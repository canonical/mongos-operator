#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from ..helpers import wait_for_mongos_units_blocked
from .helpers import (
    check_mongos_tls_enabled,
    check_mongos_tls_disabled,
    toggle_tls_mongos,
    EXTERNAL_CERT_PATH,
    INTERNAL_CERT_PATH,
    get_file_contents,
    check_certs_correctly_distributed,
    time_file_created,
    time_process_started,
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
    await build_cluster(ops_test)
    await deploy_tls(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_enabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can enable TLS."""
    await integrate_mongos_with_tls(ops_test)

    await wait_for_mongos_units_blocked(
        ops_test,
        MONGOS_APP_NAME,
        status="mongos has TLS enabled, but config-server does not.",
        timeout=TIMEOUT,
    )

    await integrate_cluster_with_tls(ops_test)

    await check_mongos_tls_enabled(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_rotate_certs(ops_test: OpsTest) -> None:
    await rotate_and_verify_certs(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_disabled(ops_test: OpsTest) -> None:
    """Tests that mongos charm can disable TLS."""
    await toggle_tls_mongos(ops_test, enable=False)
    await check_mongos_tls_disabled(ops_test)

    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        idle_period=60,
        timeout=TIMEOUT,
        raise_on_blocked=False,
    )

    for mongos_unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        assert (
            mongos_unit.workload_status_message == "mongos requires TLS to be enabled."
        ), "mongos fails to report TLS inconsistencies."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_tls_reenabled(ops_test: OpsTest) -> None:
    """Test that mongos can enable TLS after being integrated to cluster ."""
    await toggle_tls_mongos(ops_test, enable=True)
    await check_mongos_tls_enabled(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_tls_ca_mismatch(ops_test: OpsTest) -> None:
    """Tests that mongos charm can disable TLS."""
    await toggle_tls_mongos(ops_test, enable=False)
    await ops_test.model.deploy(
        CERTS_APP_NAME, application_name=DIFFERENT_CERTS_APP_NAME, channel="edge"
    )
    await ops_test.model.wait_for_idle(
        apps=[DIFFERENT_CERTS_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
        status="active",
        timeout=TIMEOUT,
    )

    await toggle_tls_mongos(
        ops_test, enable=True, certs_app_name=DIFFERENT_CERTS_APP_NAME
    )

    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
        timeout=TIMEOUT,
    )

    await wait_for_mongos_units_blocked(
        ops_test,
        MONGOS_APP_NAME,
        status="mongos CA and Config-Server CA don't match.",
        timeout=TIMEOUT,
    )


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
        channel="6/stable",
        revision=173,
        config={"role": "config-server"},
    )
    await ops_test.model.deploy(
        MONGODB_CHARM_NAME,
        application_name=SHARD_APP_NAME,
        channel="6/stable",
        revision=173,
        config={"role": "shard"},
    )

    await ops_test.model.wait_for_idle(
        apps=[APPLICATION_APP_NAME, SHARD_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=10,
        raise_on_blocked=False,
        timeout=TIMEOUT,
    )

    await ops_test.model.integrate(APPLICATION_APP_NAME, MONGOS_APP_NAME)
    await wait_for_mongos_units_blocked(ops_test, MONGOS_APP_NAME, timeout=TIMEOUT)


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
    await ops_test.model.deploy(CERTS_APP_NAME, channel="edge")

    await ops_test.model.wait_for_idle(
        apps=[CERTS_APP_NAME, CONFIG_SERVER_APP_NAME],
        idle_period=20,
        raise_on_blocked=False,
        timeout=TIMEOUT,
        raise_on_error=False,
    )


async def integrate_mongos_with_tls(ops_test: OpsTest) -> None:
    """Integrate mongos to the TLS interface."""
    await ops_test.model.integrate(
        f"{MONGOS_APP_NAME}:{CERT_REL_NAME}",
        f"{CERTS_APP_NAME}:{CERT_REL_NAME}",
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


async def rotate_and_verify_certs(ops_test: OpsTest) -> None:
    """Verifies that each unit is able to rotate their TLS certificates."""
    original_tls_info = {}
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        original_tls_info[unit.name] = {}

        original_tls_info[unit.name][
            "external_cert_contents"
        ] = await get_file_contents(ops_test, unit, EXTERNAL_CERT_PATH)
        original_tls_info[unit.name][
            "internal_cert_contents"
        ] = await get_file_contents(ops_test, unit, INTERNAL_CERT_PATH)
        original_tls_info[unit.name]["external_cert_time"] = await time_file_created(
            ops_test, unit.name, EXTERNAL_CERT_PATH
        )
        original_tls_info[unit.name]["internal_cert_time"] = await time_file_created(
            ops_test, unit.name, INTERNAL_CERT_PATH
        )
        original_tls_info[unit.name]["mongos_service"] = await time_process_started(
            ops_test, unit.name, MONGOS_SERVICE
        )
        await check_certs_correctly_distributed(
            ops_test, unit, app_name=MONGOS_APP_NAME
        )

    # set external and internal key using auto-generated key for each unit
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        action = await unit.run_action(action_name="set-tls-private-key")
        action = await action.wait()
        assert action.status == "completed", "setting external and internal key failed."

    # wait for certificate to be available and processed. Can get receive two certificate
    # available events and restart twice so we want to ensure we are idle for at least 1 minute
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME], status="active", timeout=1000, idle_period=60
    )

    # After updating both the external key and the internal key a new certificate request will be
    # made; then the certificates should be available and updated.
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        new_external_cert = await get_file_contents(ops_test, unit, EXTERNAL_CERT_PATH)
        new_internal_cert = await get_file_contents(ops_test, unit, INTERNAL_CERT_PATH)

        new_external_cert_time = await time_file_created(
            ops_test, unit.name, EXTERNAL_CERT_PATH
        )
        new_internal_cert_time = await time_file_created(
            ops_test, unit.name, INTERNAL_CERT_PATH
        )
        new_mongos_service_time = await time_process_started(
            ops_test, unit.name, MONGOS_SERVICE
        )

        await check_certs_correctly_distributed(
            ops_test, unit, app_name=MONGOS_APP_NAME
        )

        assert (
            new_external_cert != original_tls_info[unit.name]["external_cert_contents"]
        ), "external cert not rotated"

        assert (
            new_internal_cert != original_tls_info[unit.name]["external_cert_contents"]
        ), "external cert not rotated"
        assert (
            new_external_cert_time > original_tls_info[unit.name]["external_cert_time"]
        ), f"external cert for {unit.name} was not updated."
        assert (
            new_internal_cert_time > original_tls_info[unit.name]["internal_cert_time"]
        ), f"internal cert for {unit.name} was not updated."

        # Once the certificate requests are processed and updated the mongos.service should be
        # restarted
        assert (
            new_mongos_service_time > original_tls_info[unit.name]["mongos_service"]
        ), f"mongos service for {unit.name} was not restarted."

    # Verify that TLS is functioning on all units.
    for unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        await check_mongos_tls_enabled(ops_test)
