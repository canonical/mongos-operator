#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from .helpers import check_mongos

APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"
CLUSTER_REL_NAME = "cluster"

CONFIG_SERVER_APP_NAME = "config-server"
SHARD_APP_NAME = "shard"
SHARD_REL_NAME = "sharding"
CONFIG_SERVER_REL_NAME = "config-server"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    application_charm = await ops_test.build_charm("tests/integration/application")
    mongos_charm = await ops_test.build_charm(".")

    await ops_test.model.deploy(
        application_charm,
        application_name=APPLICATION_APP_NAME,
    )
    await ops_test.model.deploy(
        mongos_charm,
        num_units=0,
        application_name=MONGOS_APP_NAME,
    )

    await ops_test.model.wait_for_idle(
        apps=[
            APPLICATION_APP_NAME,
        ],
        idle_period=10,
        raise_on_blocked=False,
    )


@pytest.mark.abort_on_fail
async def test_waits_for_config_server(ops_test: OpsTest) -> None:
    """Verifies that the application and unit are active."""
    await ops_test.model.add_relation(APPLICATION_APP_NAME, MONGOS_APP_NAME)

    # verify that Charmed MongoDB is blocked and reports incorrect credentials
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        status="blocked",
        idle_period=10,
    ),

    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    assert mongos_unit.workload_status_message == "Missing relation to config-server."


@pytest.mark.abort_on_fail
# wait for 6/edge charm on mongodb to be updated before running this test on CI
@pytest.mark.skip()
async def test_mongos_starts_with_config_server(ops_test: OpsTest) -> None:
    # prepare sharded cluster
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
    )
    await ops_test.model.integrate(
        f"{SHARD_APP_NAME}:{SHARD_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CONFIG_SERVER_REL_NAME}",
    )
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
    )

    # connect sharded cluster to mongos
    await ops_test.model.integrate(
        f"{MONGOS_APP_NAME}:{CLUSTER_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CLUSTER_REL_NAME}",
    )
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME, MONGOS_APP_NAME],
        idle_period=20,
        status="active",
    )

    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(ops_test, mongos_unit, auth=False)
    assert mongos_running, "Mongos is not currently running."


@pytest.mark.abort_on_fail
# wait for 6/edge charm on mongodb to be updated before running this test on CI
@pytest.mark.skip()
async def test_mongos_has_user(ops_test: OpsTest) -> None:
    # prepare sharded cluster
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(ops_test, mongos_unit, auth=True)
    assert mongos_running, "Mongos is not currently running."
