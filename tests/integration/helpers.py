from charms.mongodb.v1.helpers import MONGO_SHELL
from pytest_operator.plugin import OpsTest
import ops
import json
import yaml
import subprocess

from typing import Optional, Dict

from tenacity import (
    Retrying,
    stop_after_delay,
    wait_fixed,
)

APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"
CLUSTER_REL_NAME = "cluster"
MONGODB_CHARM_NAME = "mongodb"

CONFIG_SERVER_APP_NAME = "config-server"
SHARD_APP_NAME = "shard"
SHARD_REL_NAME = "sharding"
CONFIG_SERVER_REL_NAME = "config-server"

MONGOS_SOCKET = "%2Fvar%2Fsnap%2Fcharmed-mongodb%2Fcommon%2Fvar%2Fmongodb-27018.sock"
MONGOS_APP_NAME = "mongos"
PING_CMD = "db.runCommand({ping: 1})"


async def generate_mongos_command(
    ops_test: OpsTest,
    auth: bool,
    app_name: Optional[str],
    uri: str = None,
    external: bool = False,
) -> str:
    """Generates a command which verifies mongos is running."""
    mongodb_uri = uri or await generate_mongos_uri(ops_test, auth, app_name, external)
    return f"{MONGO_SHELL} '{mongodb_uri}'  --eval '{PING_CMD}'"


async def check_mongos(
    ops_test: OpsTest,
    unit: ops.model.Unit,
    auth: bool,
    app_name: Optional[str] = None,
    uri: str = None,
    external: bool = False,
) -> bool:
    """Returns whether mongos is running on the provided unit."""
    mongos_check = await generate_mongos_command(
        ops_test, auth, app_name, uri, external
    )

    # since mongos is communicating only via the unix domain socket, we cannot connect to it via
    # traditional pymongo methods
    check_cmd = f"exec --unit {unit.name} -- {mongos_check}"
    return_code, _, _ = await ops_test.juju(*check_cmd.split())
    return return_code == 0


async def run_mongos_command(
    ops_test: OpsTest, unit: ops.model.Unit, mongos_cmd: str, app_name: str
):
    """Runs the provided mongos command.

    The mongos charm uses the unix domain socket to communicate, and therefore we cannot run
    MongoDB commands from outside the unit and we must use `juju exec` instead.
    """
    mongodb_uri = await generate_mongos_uri(ops_test, auth=True, app_name=app_name)

    check_cmd = [
        "exec",
        "--unit",
        unit.name,
        "--",
        MONGO_SHELL,
        f"'{mongodb_uri}'",
        "--eval",
        f"'{mongos_cmd}'",
    ]
    return_code, std_output, std_err = await ops_test.juju(*check_cmd)
    return (return_code, std_output, std_err)


async def generate_mongos_uri(
    ops_test: OpsTest,
    auth: bool,
    app_name: Optional[str] = None,
    external: bool = False,
) -> str:
    """Generates a URI for accessing mongos."""
    host = (
        MONGOS_SOCKET
        if not external
        else f"{await get_ip_address(ops_test, app_name=MONGOS_APP_NAME)}:27018"
    )
    if not auth:
        return f"mongodb://{host}"

    secret_uri = await get_application_relation_data(
        ops_test, app_name, "mongos", "secret-user"
    )

    secret_data = await get_secret_data(ops_test, secret_uri)
    return secret_data.get("uris")


async def get_secret_data(ops_test, secret_uri) -> Dict:
    """Returns secret relation data."""
    secret_unique_id = secret_uri.split("/")[-1]
    complete_command = f"show-secret {secret_uri} --reveal --format=json"
    _, stdout, _ = await ops_test.juju(*complete_command.split())
    return json.loads(stdout)[secret_unique_id]["content"]["Data"]


async def get_application_relation_data(
    ops_test: OpsTest,
    application_name: str,
    relation_name: str,
    key: str,
    relation_id: str = None,
    relation_alias: str = None,
) -> Optional[str]:
    """Get relation data for an application.

    Args:
        ops_test: The ops test framework instance
        application_name: The name of the application
        relation_name: name of the relation to get connection data from
        key: key of data to be retrieved
        relation_id: id of the relation to get connection data from
        relation_alias: alias of the relation (like a connection name)
            to get connection data from
    Returns:
        the that that was requested or None
            if no data in the relation
    Raises:
        ValueError if it's not possible to get application unit data
            or if there is no data for the particular relation endpoint
            and/or alias.
    """
    unit = ops_test.model.applications[application_name].units[0]
    raw_data = (await ops_test.juju("show-unit", unit.name))[1]
    if not raw_data:
        raise ValueError(f"no unit info could be grabbed for { unit.name}")
    data = yaml.safe_load(raw_data)

    # Filter the data based on the relation name.
    relation_data = [
        v for v in data[unit.name]["relation-info"] if v["endpoint"] == relation_name
    ]
    if relation_id:
        # Filter the data based on the relation id.
        relation_data = [v for v in relation_data if v["relation-id"] == relation_id]

    if relation_alias:
        # Filter the data based on the cluster/relation alias.
        relation_data = [
            v
            for v in relation_data
            if json.loads(v["application-data"]["data"])["alias"] == relation_alias
        ]

    if len(relation_data) == 0:
        raise ValueError(
            f"no relation data could be grabbed on relation with endpoint {relation_name} and alias {relation_alias}"
        )

    return relation_data[0]["application-data"].get(key)


async def get_ip_address(ops_test, app_name=MONGOS_APP_NAME) -> str:
    """Returns an IP address of the fist unit of a provided application."""
    app_unit = ops_test.model.applications[app_name].units[0]
    return await app_unit.get_public_address()


async def get_unit_hostname(ops_test: OpsTest, unit_id: int, app: str) -> str:
    """Get the hostname of a specific unit."""
    _, hostname, _ = await ops_test.juju("ssh", f"{app}/{unit_id}", "hostname")
    return hostname.strip()


def get_juju_status(model_name: str, app_name: str) -> str:
    return subprocess.check_output(
        f"juju status --model {model_name} {app_name}".split()
    ).decode("utf-8")


async def check_all_units_blocked_with_status(
    ops_test: OpsTest, app_name: str, status: Optional[str]
) -> None:
    """Checks if all units are blocked with a provided status.

    The command juju status --model {model-name} {app-name} --json does not provide information
    for statuses for subordinate charms like it does for normal charms. Specifically when
    converting to json it lose this information. To get this information we must parse the status
    manually.
    """
    juju_status = (
        subprocess.check_output(
            f"juju status --model {ops_test.model.info.name} {app_name}".split()
        )
        .decode("utf-8")
        .split("\n")
    )

    for status_item in juju_status:
        if app_name not in status_item:
            continue
        # no need to check that status of the application since the application can have a
        # different status than the units.
        is_app = "/" not in status_item
        if is_app:
            continue

        status_item = status_item.split()
        unit_name = status_item[0]
        status_type = status_item[1]
        status_message = " ".join(status_item[4:])
        assert (
            status_type == "blocked"
        ), f"unit {unit_name} not in blocked state, in {status_type}"

        if status:
            assert (
                status_message == status
            ), f"unit {unit_name} does not show the status {status}"


async def wait_for_mongos_units_blocked(
    ops_test: OpsTest, app_name: str, status: Optional[str] = None, timeout=20
) -> None:
    """Waits for units of mongos to be in the blocked state.

    This is necessary because the MongoDB app can report a different status than the units.
    """
    hook_interval_key = "update-status-hook-interval"
    try:
        old_interval = (await ops_test.model.get_config())[hook_interval_key]
        await ops_test.model.set_config({hook_interval_key: "1m"})
        for attempt in Retrying(
            stop=stop_after_delay(timeout), wait=wait_fixed(1), reraise=True
        ):
            with attempt:
                await check_all_units_blocked_with_status(ops_test, app_name, status)
    finally:
        await ops_test.model.set_config({hook_interval_key: old_interval})


async def deploy_cluster_components(
    ops_test: OpsTest, channel: str | None = None
) -> None:
    """Deploys all cluster components and waits for idle."""
    application_charm = await ops_test.build_charm("tests/integration/application")
    if not channel:
        mongos_charm = await ops_test.build_charm(".")
    else:
        mongos_charm = MONGOS_APP_NAME

    await ops_test.model.deploy(
        application_charm,
        num_units=2,
        application_name=APPLICATION_APP_NAME,
    )
    await ops_test.model.deploy(
        mongos_charm,
        num_units=0,
        channel=channel,
        application_name=MONGOS_APP_NAME,
    )
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=CONFIG_SERVER_APP_NAME,
        channel="6/edge",
        revision=192,
        config={"role": "config-server"},
    )
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=SHARD_APP_NAME,
        channel="6/edge",
        revision=192,
        config={"role": "shard"},
    )

    await ops_test.model.wait_for_idle(
        apps=[APPLICATION_APP_NAME, SHARD_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
    )


async def integrate_cluster_components(ops_test: OpsTest) -> None:
    """Integrates all cluster components and waits for idle."""
    await ops_test.model.integrate(APPLICATION_APP_NAME, MONGOS_APP_NAME)

    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
    )
    await ops_test.model.integrate(
        f"{SHARD_APP_NAME}:{SHARD_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CONFIG_SERVER_REL_NAME}",
    )

    await ops_test.model.integrate(
        f"{MONGOS_APP_NAME}:{CLUSTER_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CLUSTER_REL_NAME}",
    )
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME, MONGOS_APP_NAME],
        idle_period=20,
        status="active",
    )
