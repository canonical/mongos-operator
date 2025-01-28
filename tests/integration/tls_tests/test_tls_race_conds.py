#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from .helpers import (
    check_mongos_tls_enabled,
)
from .test_tls import (
    deploy_cluster,
    deploy_tls,
    build_cluster,
    integrate_cluster_with_tls,
    integrate_mongos_with_tls,
)

MONGOS_SERVICE = "snap.charmed-mongodb.mongos.service"
APPLICATION_APP_NAME = "application"
MONGOS_APP_NAME = "mongos"
MONGODB_CHARM_NAME = "mongodb"
CONFIG_SERVER_APP_NAME = "config-server"
SHARD_APP_NAME = "shard"
CLUSTER_COMPONENTS = [CONFIG_SERVER_APP_NAME, SHARD_APP_NAME]
CERT_REL_NAME = "certificates"
SHARD_REL_NAME = "sharding"
CLUSTER_REL_NAME = "cluster"
CONFIG_SERVER_REL_NAME = "config-server"
CERTS_APP_NAME = "self-signed-certificates"
DIFFERENT_CERTS_APP_NAME = "self-signed-certificates-separate"
TIMEOUT = 15 * 60


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster(ops_test)
    await build_cluster(ops_test, integrate_with_mongos=False)
    await deploy_tls(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_enabled(ops_test: OpsTest) -> None:
    """Tests race condition: mongos charm can integrate with TLS and then the config-server."""
    await integrate_cluster_with_tls(ops_test)
    await integrate_mongos_with_tls(ops_test)

    # integrate mongos with config-server
    await ops_test.model.integrate(
        f"{MONGOS_APP_NAME}:{CLUSTER_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CLUSTER_REL_NAME}",
    )

    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        idle_period=20,
        status="active",
        timeout=TIMEOUT,
    )

    await check_mongos_tls_enabled(ops_test)
