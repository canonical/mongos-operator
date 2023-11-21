#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import asyncio
import pytest
from pytest_operator.plugin import OpsTest

APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, application_charm, mongos_charm) -> None:
    """Build and deploy a sharded cluster."""
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
    await asyncio.gather(
        ops_test.model.wait_for_idle(
            apps=[MONGOS_APP_NAME],
            status="blocked",
            idle_period=10,
        ),
    )

    config_server_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    assert config_server_unit.workload_status_message == "missing relation to config-server"
