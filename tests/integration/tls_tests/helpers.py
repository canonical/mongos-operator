#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from pytest_operator.plugin import OpsTest
from ..helpers import get_application_relation_data, get_secret_data
from tenacity import RetryError, Retrying, stop_after_attempt, wait_exponential
from datetime import datetime
from typing import Optional, Dict
import json
import ops


MONGODB_SNAP_DATA_DIR = "/var/snap/charmed-mongodb/current"
MONGOD_CONF_DIR = f"{MONGODB_SNAP_DATA_DIR}/etc/mongod"
MONGO_COMMON_DIR = "/var/snap/charmed-mongodb/common"
EXTERNAL_PEM_PATH = f"{MONGOD_CONF_DIR}/external-cert.pem"
EXTERNAL_CERT_PATH = f"{MONGOD_CONF_DIR}/external-ca.crt"
INTERNAL_CERT_PATH = f"{MONGOD_CONF_DIR}/internal-ca.crt"
MONGO_SHELL = "charmed-mongodb.mongosh"
MONGOS_APP_NAME = "mongos"
CERT_REL_NAME = "certificates"
CERTS_APP_NAME = "self-signed-certificates"


class ProcessError(Exception):
    """Raised when a process fails."""


async def check_mongos_tls_disabled(ops_test: OpsTest) -> None:
    # check mongos is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=False)


async def check_mongos_tls_enabled(ops_test: OpsTest) -> None:
    # check each replica set is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=True)


async def toggle_tls_mongos(
    ops_test: OpsTest, enable: bool, certs_app_name: str = CERTS_APP_NAME
) -> None:
    """Toggles TLS on mongos application to the specified enabled state."""
    if enable:
        await ops_test.model.integrate(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{certs_app_name}:{CERT_REL_NAME}",
        )
    else:
        await ops_test.model.applications[MONGOS_APP_NAME].remove_relation(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{certs_app_name}:{CERT_REL_NAME}",
        )


async def mongos_tls_command(ops_test: OpsTest) -> str:
    """Generates a command which verifies TLS status."""
    secret_uri = await get_application_relation_data(
        ops_test, MONGOS_APP_NAME, "mongos", "secret-user"
    )

    secret_data = await get_secret_data(ops_test, secret_uri)
    client_uri = secret_data.get("uris")

    return (
        f"{MONGO_SHELL} '{client_uri}'  --eval 'sh.status()'"
        f" --tls --tlsCAFile {EXTERNAL_CERT_PATH}"
        f" --tlsCertificateKeyFile {EXTERNAL_PEM_PATH}"
    )


async def check_tls(ops_test, unit, enabled) -> None:
    """Returns True if TLS matches the expected state "enabled"."""
    try:
        for attempt in Retrying(
            stop=stop_after_attempt(10),
            wait=wait_exponential(multiplier=1, min=2, max=30),
        ):
            with attempt:
                mongod_tls_check = await mongos_tls_command(ops_test)
                check_tls_cmd = f"exec --unit {unit.name} -- {mongod_tls_check}"
                return_code, _, _ = await ops_test.juju(*check_tls_cmd.split())

                tls_enabled = return_code == 0
                if enabled != tls_enabled:
                    raise ValueError(
                        f"TLS is{' not' if not tls_enabled else ''} enabled on {unit.name}"
                    )
                return True
    except RetryError:
        return False


async def time_file_created(ops_test: OpsTest, unit_name: str, path: str) -> int:
    """Returns the unix timestamp of when a file was created on a specified unit."""
    time_cmd = f"exec --unit {unit_name} --  ls -l --time-style=full-iso {path} "
    return_code, ls_output, _ = await ops_test.juju(*time_cmd.split())

    if return_code != 0:
        raise ProcessError(
            "Expected time command %s to succeed instead it failed: %s",
            time_cmd,
            return_code,
        )

    return process_ls_time(ls_output)


async def time_process_started(
    ops_test: OpsTest, unit_name: str, process_name: str
) -> int:
    """Retrieves the time that a given process started according to systemd."""
    time_cmd = f"exec --unit {unit_name} --  systemctl show {process_name} --property=ActiveEnterTimestamp"
    return_code, systemctl_output, _ = await ops_test.juju(*time_cmd.split())

    if return_code != 0:
        raise ProcessError(
            "Expected time command %s to succeed instead it failed: %s",
            time_cmd,
            return_code,
        )

    return process_systemctl_time(systemctl_output)


async def check_certs_correctly_distributed(
    ops_test: OpsTest, unit: ops.Unit, app_name=None
) -> None:
    """Comparing expected vs distributed certificates.

    Verifying certificates downloaded on the charm against the ones distributed by the TLS operator
    """
    app_name = app_name
    unit_secret_id = await get_secret_id(ops_test, unit.name)
    unit_secret_content = await get_secret_content(ops_test, unit_secret_id)

    # Get the values for certs from the relation, as provided by TLS Charm
    certificates_raw_data = await get_application_relation_data(
        ops_test, app_name, CERT_REL_NAME, "certificates"
    )
    certificates_data = json.loads(certificates_raw_data)

    # compare the TLS resources stored on the disk of the unit with the ones from the TLS relation
    for cert_type, cert_path in [
        ("int", INTERNAL_CERT_PATH),
        ("ext", EXTERNAL_CERT_PATH),
    ]:
        unit_csr = unit_secret_content[f"{cert_type}-csr-secret"]
        tls_item = [
            data
            for data in certificates_data
            if data["certificate_signing_request"].rstrip() == unit_csr.rstrip()
        ][0]

        # Read the content of the cert file stored in the unit
        cert_file_content = await get_file_content(ops_test, unit.name, cert_path)

        # Get the external cert value from the relation
        relation_cert = "\n".join(tls_item["chain"]).strip()

        # confirm that they match
        assert (
            relation_cert == cert_file_content
        ), f"Relation Content for {cert_type}-cert:\n{relation_cert}\nFile Content:\n{cert_file_content}\nMismatch."


async def get_file_content(ops_test: OpsTest, unit_name: str, filepath: str) -> str:
    """Returns the contents of the provided filepath."""
    cat_cmd = f"exec --unit {unit_name} -- sudo cat {filepath}"
    _, stdout, _ = await ops_test.juju(*cat_cmd.split(), check=True)
    return stdout.strip()


def process_ls_time(ls_output):
    """Parse time representation as returned by the 'ls' command."""
    time_as_str = "T".join(ls_output.split("\n")[0].split(" ")[5:7])
    # further strip down additional milliseconds
    time_as_str = time_as_str[0:-3]
    d = datetime.strptime(time_as_str, "%Y-%m-%dT%H:%M:%S.%f")
    return d


def process_systemctl_time(systemctl_output):
    """Parse time representation as returned by the 'systemctl' command."""
    "ActiveEnterTimestamp=Thu 2022-09-22 10:00:00 UTC"
    time_as_str = "T".join(systemctl_output.split("=")[1].split(" ")[1:3])
    d = datetime.strptime(time_as_str, "%Y-%m-%dT%H:%M:%S")
    return d


async def get_secret_id(ops_test, app_or_unit: Optional[str] = None) -> str:
    """Retrieve secret ID for an app or unit."""
    complete_command = "list-secrets"

    if app_or_unit:
        prefix = "unit" if app_or_unit[-1].isdigit() else "application"
        formated_app_or_unit = f"{prefix}-{app_or_unit}"
        if prefix == "unit":
            formated_app_or_unit = formated_app_or_unit.replace("/", "-")
        complete_command += f" --owner {formated_app_or_unit}"

    _, stdout, _ = await ops_test.juju(*complete_command.split())
    output_lines_split = [line.split() for line in stdout.strip().split("\n")]
    if app_or_unit:
        return [line[0] for line in output_lines_split if app_or_unit in line][0]

    return output_lines_split[1][0]


async def get_secret_content(ops_test, secret_id) -> Dict[str, str]:
    """Retrieve contents of a Juju Secret."""
    secret_id = secret_id.split("/")[-1]
    complete_command = f"show-secret {secret_id} --reveal --format=json"
    _, stdout, _ = await ops_test.juju(*complete_command.split())
    data = json.loads(stdout)
    return data[secret_id]["content"]["Data"]


async def get_file_contents(ops_test: OpsTest, unit: str, filepath: str) -> str:
    """Returns the contents of the provided filepath."""
    mv_cmd = f"exec --unit {unit.name} sudo cat {filepath} "
    _, stdout, _ = await ops_test.juju(*mv_cmd.split())
    return stdout
