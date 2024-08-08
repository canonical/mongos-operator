#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from ..helpers import check_mongos, wait_for_mongos_units_blocked


DATA_INTEGRATOR_APP_NAME = "data-integrator"
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

    mongos_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(
        DATA_INTEGRATOR_APP_NAME,
        channel="latest/edge",
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
        revision=173,
        config={"role": "config-server"},
    )
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=SHARD_APP_NAME,
        channel="6/edge",
        revision=173,
        config={"role": "shard"},
    )

    await ops_test.model.wait_for_idle(
        apps=[DATA_INTEGRATOR_APP_NAME, SHARD_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
    )


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_starts_with_config_server(ops_test: OpsTest) -> None:
    """Verify mongos is running and can be accessed externally via IP-address."""
    # mongos cannot start until it has a host application
    await ops_test.model.applications[DATA_INTEGRATOR_APP_NAME].set_config(
        {
            "database-name": "test-database",
        }
    )

    await ops_test.model.add_relation(DATA_INTEGRATOR_APP_NAME, MONGOS_APP_NAME)
    await wait_for_mongos_units_blocked(ops_test, MONGOS_APP_NAME, timeout=300)
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
    mongos_running = await check_mongos(
        ops_test, mongos_unit, auth=False, external=True
    )
    assert mongos_running, "Mongos is not currently running."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_has_user(ops_test: OpsTest) -> None:
    """Verify mongos has user and is able to connect externally via IP-address."""
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(
        ops_test,
        mongos_unit,
        app_name=DATA_INTEGRATOR_APP_NAME,
        auth=True,
        external=True,
    )
    assert mongos_running, "Mongos is not currently running."
