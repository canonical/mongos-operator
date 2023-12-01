from charms.mongodb.v1.helpers import MONGO_SHELL
from pytest_operator.plugin import OpsTest
import ops

MONGOS_URI = (
    "mongodb://%2Fvar%2Fsnap%2Fcharmed-mongodb%2Fcommon%2Fvar%2Fmongodb-27018.sock"
)
MONGOS_APP_NAME = "mongos"


async def mongos_command(ops_test: OpsTest) -> str:
    """Generates a command which verifies TLS status."""
    return f"{MONGO_SHELL} '{MONGOS_URI}'  --eval 'ping'"


async def check_mongos(ops_test: OpsTest, unit: ops.model.Unit) -> bool:
    """Returns whether mongos is running on the provided unit."""
    mongos_check = await mongos_command(ops_test)
    check_tls_cmd = f"exec --unit {unit.name} -- {mongos_check}"
    return_code, _, _ = await ops_test.juju(*check_tls_cmd.split())
    mongos_running = return_code == 0
    return mongos_running
