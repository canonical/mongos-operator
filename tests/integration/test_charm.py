#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from .helpers import check_mongos

APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"
CLUSTER_REL_NAME = "cluster"
MONGODB_CHARM_NAME = "mongodb"

CONFIG_SERVER_APP_NAME = "config-server"
SHARD_APP_NAME = "shard"
SHARD_REL_NAME = "sharding"
CONFIG_SERVER_REL_NAME = "config-server"


@pytest.mark.group(1)
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
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=CONFIG_SERVER_APP_NAME,
        channel="6/edge",
        revision=142,
        config={"role": "config-server"},
    )
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=SHARD_APP_NAME,
        channel="6/edge",
        revision=142,
        config={"role": "shard"},
    )

    await ops_test.model.wait_for_idle(
        apps=[APPLICATION_APP_NAME, SHARD_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
    )


@pytest.mark.group(1)
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


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
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


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_has_user(ops_test: OpsTest) -> None:
    # prepare sharded cluster
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(ops_test, mongos_unit, auth=True)
    assert mongos_running, "Mongos is not currently running."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_updates_config_db(ops_test: OpsTest) -> None:
    # completely change the hosts that mongos was connected to
    await ops_test.model.applications[CONFIG_SERVER_APP_NAME].add_units(count=1)
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME],
        status="active",
        timeout=1000,
    )

    # destroy the unit we were initially connected to
    await ops_test.model.applications[CONFIG_SERVER_APP_NAME].destroy_units(
        f"{CONFIG_SERVER_APP_NAME}/0"
    )
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME],
        status="active",
        timeout=1000,
    )

    # prepare sharded cluster
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(ops_test, mongos_unit, auth=True)
    assert mongos_running, "Mongos is not currently running."
