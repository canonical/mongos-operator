#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest


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


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster()
    await build_cluster()
    await deploy_tls()


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_enabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can enable TLS."""
    await integrate_cluster_with_tls(ops_test)
    await check_mongos_tls_enabled(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_rotated(ops_test: OpsTest) -> None:
    """Tests that mongos charm can rotate TLS certs."""


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_disabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can disable TLS."""
    await toggle_tls_mongos(ops_test, enable=False)
    await check_mongos_tls_disabled(ops_test)


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
    )

    await ops_test.model.add_relation(APPLICATION_APP_NAME, MONGOS_APP_NAME)
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        status="blocked",
        idle_period=10,
    )


async def build_cluster(ops_test: OpsTest) -> None:
    """Connects the cluster components to each other."""
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
            apps=CLUSTER_COMPONENTS,
            idle_period=20,
            timeout=TIMEOUT,
            raise_on_blocked=False,
            status="active",
        )


async def check_mongos_tls_disabled(ops_test: OpsTest) -> None:
    # check mongos is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=False)


async def check_mongos_tls_enabled(ops_test: OpsTest) -> None:
    # check each replica set is running with TLS enabled
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_tls(ops_test, unit, enabled=True)


async def toggle_tls_mongos(ops_test: OpsTest, enable: bool) -> None:
    """Toggles TLS on mongos application to the specified enabled state."""
    if enable:
        await ops_test.model.integrate(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
        )
    else:
        await ops_test.model.applications[MONGOS_APP_NAME].remove_relation(
            f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
            f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
        )


from ..helpers import get_application_relation_data, get_secret_data

from tenacity import RetryError, Retrying, stop_after_attempt, wait_exponential

MONGODB_SNAP_DATA_DIR = "/var/snap/charmed-mongodb/current"
MONGOD_CONF_DIR = f"{MONGODB_SNAP_DATA_DIR}/etc/mongod"
MONGO_COMMON_DIR = "/var/snap/charmed-mongodb/common"
EXTERNAL_PEM_PATH = f"{MONGOD_CONF_DIR}/external-cert.pem"
EXTERNAL_CERT_PATH = f"{MONGOD_CONF_DIR}/external-ca.crt"
MONGO_SHELL = "charmed-mongodb.mongosh"


async def mongos_tls_command(ops_test: OpsTest) -> str:
    """Generates a command which verifies TLS status."""
    secret_uri = await get_application_relation_data(
        ops_test, MONGOS_APP_NAME, "mongos", "secret-user"
    )

    secret_data = await get_secret_data(ops_test, secret_uri)
    client_uri = secret_data.get("uris")

    return (
        f"{MONGO_SHELL} '{client_uri}'  --eval 'sh.status()'"
        f" --tls --tlsCAFile {EXTERNAL_CERT_PATH}"
        f" --tlsCertificateKeyFile {EXTERNAL_PEM_PATH}"
    )


async def check_tls(ops_test, unit, enabled) -> None:
    try:
        for attempt in Retrying(
            stop=stop_after_attempt(10), wait=wait_exponential(multiplier=1, min=2, max=30)
        ):
            with attempt:
                mongod_tls_check = await mongos_tls_command(ops_test)
                check_tls_cmd = f"exec --unit {unit.name} -- {mongod_tls_check}"
                return_code, _, _ = await ops_test.juju(*check_tls_cmd.split())

                tls_enabled = return_code == 0
                if enabled != tls_enabled:
                    raise ValueError(
                        f"TLS is{' not' if not tls_enabled else ''} enabled on {unit.name}"
                    )
                return True
    except RetryError:
        return False
