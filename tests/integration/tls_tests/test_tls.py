#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from .helpers import (
    check_mongos_tls_enabled,
    check_mongos_tls_disabled,
    toggle_tls_mongos,
)


APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"
MONGODB_CHARM_NAME = "mongodb"
CONFIG_SERVER_APP_NAME = "config-server"
SHARD_APP_NAME = "shard"
CLUSTER_COMPONENTS = [MONGOS_APP_NAME, CONFIG_SERVER_APP_NAME, SHARD_APP_NAME]
CERT_REL_NAME = "certificates"
SHARD_REL_NAME = "sharding"
CLUSTER_REL_NAME = "cluster"
CONFIG_SERVER_REL_NAME = "config-server"
CERTS_APP_NAME = "self-signed-certificates"
TIMEOUT = 15 * 60


@pytest.mark.skip("Wait new MongoDB charm is published.")
@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster(ops_test)
    await build_cluster(ops_test)
    await deploy_tls(ops_test)


@pytest.mark.skip("Wait new MongoDB charm is published.")
@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_enabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can enable TLS."""
    # await integrate_cluster_with_tls(ops_test)
    await check_mongos_tls_enabled(ops_test)


@pytest.mark.skip("Wait until TLS sanity check functionality is implemented")
@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_disabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can disable TLS."""
    await toggle_tls_mongos(ops_test, enable=False)
    await check_mongos_tls_disabled(ops_test)


@pytest.mark.skip("Wait until TLS sanity check functionality is implemented")
@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_tls_reenabled(ops_test: OpsTest) -> None:
    """Test that mongos can enable TLS after being integrated to cluster ."""
    await toggle_tls_mongos(ops_test, enable=True)
    await check_mongos_tls_enabled(ops_test)


async def deploy_cluster(ops_test: OpsTest) -> None:
    """Deploys the necessary cluster components"""
    application_charm = await ops_test.build_charm("tests/integration/application")

    mongos_charm = await ops_test.build_charm(".")
    await ops_test.model.deploy(
        application_charm,
        num_units=2,
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
        timeout=TIMEOUT,
    )

    await ops_test.model.add_relation(APPLICATION_APP_NAME, MONGOS_APP_NAME)
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        status="blocked",
        idle_period=10,
        timeout=TIMEOUT,
    )


async def build_cluster(ops_test: OpsTest) -> None:
    """Connects the cluster components to each other."""
    # prepare sharded cluster
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
        timeout=TIMEOUT,
    )
    await ops_test.model.integrate(
        f"{SHARD_APP_NAME}:{SHARD_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CONFIG_SERVER_REL_NAME}",
    )
    await ops_test.model.wait_for_idle(
        apps=[CONFIG_SERVER_APP_NAME, SHARD_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
        timeout=TIMEOUT,
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
        timeout=TIMEOUT,
    )


async def deploy_tls(ops_test: OpsTest) -> None:
    """Deploys the self-signed certificate operator."""
    await ops_test.model.deploy(CERTS_APP_NAME, channel="stable")

    await ops_test.model.wait_for_idle(
        apps=[CERTS_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
        timeout=TIMEOUT,
        raise_on_error=False,
    )


async def integrate_cluster_with_tls(ops_test: OpsTest) -> None:
    """Integrate cluster components to the TLS interface."""
    for cluster_component in CLUSTER_COMPONENTS:
        await ops_test.model.integrate(
            f"{cluster_component}:{CERT_REL_NAME}",
            f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
        )

    await ops_test.model.wait_for_idle(
        apps=[CLUSTER_COMPONENTS],
        idle_period=20,
        timeout=TIMEOUT,
        raise_on_blocked=False,
        status="active",
    )
