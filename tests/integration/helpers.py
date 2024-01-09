from charms.mongodb.v1.helpers import MONGO_SHELL
from pytest_operator.plugin import OpsTest
import ops
import json
import yaml
from typing import Optional, Dict

MONGOS_SOCKET = "%2Fvar%2Fsnap%2Fcharmed-mongodb%2Fcommon%2Fvar%2Fmongodb-27018.sock"
MONGOS_APP_NAME = "mongos"
PING_CMD = "db.runCommand({ping: 1})"


async def generate_mongos_command(
    ops_test: OpsTest, auth: bool, uri: str = None
) -> str:
    """Generates a command which verifies mongos is running."""
    mongodb_uri = uri or await generate_mongos_uri(ops_test, auth)
    return f"{MONGO_SHELL} '{mongodb_uri}'  --eval '{PING_CMD}'"


async def check_mongos(
    ops_test: OpsTest, unit: ops.model.Unit, auth: bool, uri: str = None
) -> bool:
    """Returns whether mongos is running on the provided unit."""
    mongos_check = await generate_mongos_command(ops_test, auth, uri)

    # since mongos is communicating only via the unix domain socket, we cannot connect to it via
    # traditional pymongo methods
    check_cmd = f"exec --unit {unit.name} -- {mongos_check}"
    return_code, _, _ = await ops_test.juju(*check_cmd.split())
    return return_code == 0


async def run_mongos_command(ops_test: OpsTest, unit: ops.model.Unit, mongos_cmd: str):
    """Runs the provided mongos command.

    The mongos charm uses the unix domain socket to communicate, and therefore we cannot run
    MongoDB commands from outside the unit and we must use `juju exec` instead.
    """
    mongodb_uri = await generate_mongos_uri(ops_test, auth=True)

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


async def generate_mongos_uri(ops_test: OpsTest, auth: bool) -> str:
    """Generates a URI for accessing mongos."""
    if not auth:
        return f"mongodb://{MONGOS_SOCKET}"

    secret_uri = await get_application_relation_data(
        ops_test, "application", "mongos_proxy", "secret-user"
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
    unit_name = f"{application_name}/0"
    raw_data = (await ops_test.juju("show-unit", unit_name))[1]

    if not raw_data:
        raise ValueError(f"no unit info could be grabbed for {unit_name}")
    data = yaml.safe_load(raw_data)

    # Filter the data based on the relation name.
    relation_data = [
        v for v in data[unit_name]["relation-info"] if v["endpoint"] == relation_name
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
