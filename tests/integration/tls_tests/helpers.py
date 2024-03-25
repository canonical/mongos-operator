#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

from pytest_operator.plugin import OpsTest
from ..helpers import get_application_relation_data, get_secret_data
from tenacity import RetryError, Retrying, stop_after_attempt, wait_exponential

MONGODB_SNAP_DATA_DIR = "/var/snap/charmed-mongodb/current"
MONGOD_CONF_DIR = f"{MONGODB_SNAP_DATA_DIR}/etc/mongod"
MONGO_COMMON_DIR = "/var/snap/charmed-mongodb/common"
EXTERNAL_PEM_PATH = f"{MONGOD_CONF_DIR}/external-cert.pem"
EXTERNAL_CERT_PATH = f"{MONGOD_CONF_DIR}/external-ca.crt"
MONGO_SHELL = "charmed-mongodb.mongosh"
MONGOS_APP_NAME = "mongos"
CERT_REL_NAME = "certificates"
CERTS_APP_NAME = "self-signed-certificates"


async def check_mongos_tls_disabled(ops_test: OpsTest) -> None:
    # check mongos is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=False)


async def check_mongos_tls_enabled(ops_test: OpsTest) -> None:
    # check each replica set is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=True)


async def toggle_tls_mongos(ops_test: OpsTest, enable: bool) -> None:
    """Toggles TLS on mongos application to the specified enabled state."""
    if enable:
        await ops_test.model.integrate(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
        )
    else:
        await ops_test.model.applications[MONGOS_APP_NAME].remove_relation(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
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
