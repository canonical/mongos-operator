#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from ..helpers import (
    deploy_cluster_components,
    integrate_cluster_components,
    MONGOS_APP_NAME,
)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster_components(ops_test, channel="6/stable")
    await integrate_cluster_components(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_upgrade(ops_test: OpsTest) -> None:
    """Tests that upgrade can be ran successfully."""
    new_charm = await ops_test.build_charm(".")
    await ops_test.model.applications[MONGOS_APP_NAME].refresh(path=new_charm)
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME], status="active", timeout=1000, idle_period=120
    )
