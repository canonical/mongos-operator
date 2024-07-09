from charms.mongodb.v1.helpers import MONGO_SHELL
from pytest_operator.plugin import OpsTest
import ops
import json
import yaml
import subprocess
from dateutil.parser import parse

from typing import Optional, Dict, Any, List

from tenacity import (
    Retrying,
    stop_after_delay,
    wait_fixed,
)

MONGOS_SOCKET = "%2Fvar%2Fsnap%2Fcharmed-mongodb%2Fcommon%2Fvar%2Fmongodb-27018.sock"
MONGOS_APP_NAME = "mongos"
PING_CMD = "db.runCommand({ping: 1})"


class Status:
    """Model class for status."""

    def __init__(self, value: str, since: str, message: Optional[str] = None):
        self.value = value
        self.since = parse(since, ignoretz=True)
        self.message = message


class Unit:
    """Model class for a Unit, with properties widely used."""

    def __init__(
        self,
        id: int,
        name: str,
        ip: str,
        hostname: str,
        is_leader: bool,
        machine_id: int,
        workload_status: Status,
        agent_status: Status,
        app_status: Status,
    ):
        self.id = id
        self.name = name
        self.ip = ip
        self.hostname = hostname
        self.is_leader = is_leader
        self.machine_id = machine_id
        self.workload_status = workload_status
        self.agent_status = agent_status
        self.app_status = app_status

    def dump(self) -> Dict[str, Any]:
        """To json."""
        result = {}
        for key, val in vars(self).items():
            result[key] = vars(val) if isinstance(val, Status) else val
        return result


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


def get_raw_application(ops_test: OpsTest, app: str) -> Dict[str, Any]:
    """Get raw application details."""
    return json.loads(
        subprocess.check_output(
            f"juju status --model {ops_test.model.info.name} {app} --format=json".split()
        )
    )["applications"][app]


async def get_application_units(ops_test: OpsTest, app: str) -> List[Unit]:
    """Get fully detailed units of an application."""
    # Juju incorrectly reports the IP addresses after the network is restored this is reported as a
    # bug here: https://github.com/juju/python-libjuju/issues/738. Once this bug is resolved use of
    # `get_unit_ip` should be replaced with `.public_address`
    raw_app = get_raw_application(ops_test, app)
    units = []
    for u_name, unit in raw_app["units"].items():
        unit_id = int(u_name.split("/")[-1])

        if not unit.get("public-address"):
            # unit not ready yet...
            continue

        unit = Unit(
            id=unit_id,
            name=u_name.replace("/", "-"),
            ip=unit["public-address"],
            hostname=await get_unit_hostname(ops_test, unit_id, app),
            is_leader=unit.get("leader", False),
            machine_id=int(unit["machine"]),
            workload_status=Status(
                value=unit["workload-status"]["current"],
                since=unit["workload-status"]["since"],
                message=unit["workload-status"].get("message"),
            ),
            agent_status=Status(
                value=unit["juju-status"]["current"],
                since=unit["juju-status"]["since"],
            ),
            app_status=Status(
                value=raw_app["application-status"]["current"],
                since=raw_app["application-status"]["since"],
                message=raw_app["application-status"].get("message"),
            ),
        )

        units.append(unit)

    return units


async def check_all_units_blocked_with_status(
    ops_test: OpsTest, db_app_name: str, status: Optional[str]
) -> None:
    # this is necessary because ops_model.units does not update the unit statuses
    for unit in await get_application_units(ops_test, db_app_name):
        assert (
            unit.workload_status.value == "blocked"
        ), f"unit {unit.name} not in blocked state, in {unit.workload_status}"
        if status:
            assert (
                unit.workload_status.message == status
            ), f"unit {unit.name} not in blocked state, in {unit.workload_status}"


async def wait_for_mongos_units_blocked(
    ops_test: OpsTest, app_name: str, status: Optional[str], timeout=20
) -> None:
    """Waits for units of mongos to be in the blocked state.

    This is necessary because the MongoDB app can report a different status than the units.
    """
    for attempt in Retrying(
        stop=stop_after_delay(timeout), wait=wait_fixed(1), reraise=True
    ):
        with attempt:
            await check_all_units_blocked_with_status(ops_test, app_name, status)
