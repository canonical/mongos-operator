#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import pytest
from pytest_operator.plugin import OpsTest
from .helpers import (
    check_mongos,
    run_mongos_command,
    get_application_relation_data,
    MONGOS_SOCKET,
    CONFIG_SERVER_REL_NAME,
    wait_for_mongos_units_blocked,
    deploy_cluster_components,
    SHARD_APP_NAME,
    APPLICATION_APP_NAME,
    CONFIG_SERVER_APP_NAME,
    CLUSTER_REL_NAME,
    MONGOS_APP_NAME,
    SHARD_REL_NAME,
)

TEST_USER_NAME = "TestUserName1"
TEST_USER_PWD = "Test123"
TEST_DB_NAME = "my-test-db"


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster_components(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_waits_for_config_server(ops_test: OpsTest) -> None:
    """Verifies that the application and unit are active."""
    await ops_test.model.integrate(APPLICATION_APP_NAME, MONGOS_APP_NAME)

    # verify that Charmed Mongos is blocked and reports incorrect credentials
    await wait_for_mongos_units_blocked(
        ops_test,
        MONGOS_APP_NAME,
        status="Missing relation to config-server.",
        timeout=300,
    )


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
    mongos_running = await check_mongos(
        ops_test, mongos_unit, app_name=APPLICATION_APP_NAME, auth=True
    )
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
    mongos_running = await check_mongos(
        ops_test, mongos_unit, app_name=APPLICATION_APP_NAME, auth=True
    )
    assert mongos_running, "Mongos is not currently running."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_user_with_extra_roles(ops_test: OpsTest) -> None:
    cmd = f'db.createUser({{user: "{TEST_USER_NAME}", pwd: "{TEST_USER_PWD}", roles: [{{role: "readWrite", db: "{TEST_DB_NAME}"}}]}});'
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    return_code, _, std_err = await run_mongos_command(
        ops_test, mongos_unit, cmd, app_name=APPLICATION_APP_NAME
    )
    assert (
        return_code == 0
    ), f"mongos user does not have correct permissions to create new user, error: {std_err}"

    test_user_uri = (
        f"mongodb://{TEST_USER_NAME}:{TEST_USER_PWD}@{MONGOS_SOCKET}/{TEST_DB_NAME}"
    )
    mongos_running = await check_mongos(
        ops_test,
        mongos_unit,
        app_name=APPLICATION_APP_NAME,
        auth=True,
        uri=test_user_uri,
    )
    assert mongos_running, "User created is not accessible."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_can_scale(ops_test: OpsTest) -> None:
    """Tests that mongos powers down when no config server is accessible."""
    # note mongos scales only when hosting application scales
    await ops_test.model.applications[APPLICATION_APP_NAME].add_units(count=1)
    await ops_test.model.wait_for_idle(
        apps=[APPLICATION_APP_NAME, MONGOS_APP_NAME],
        status="active",
        timeout=1000,
    )

    for mongos_unit in ops_test.model.applications[MONGOS_APP_NAME].units:
        mongos_running = await check_mongos(
            ops_test, mongos_unit, app_name=APPLICATION_APP_NAME, auth=True
        )
        assert mongos_running, "Mongos is not currently running."

    # destroy the unit we were initially connected to
    await ops_test.model.applications[APPLICATION_APP_NAME].destroy_units(
        f"{APPLICATION_APP_NAME}/0"
    )
    await ops_test.model.wait_for_idle(
        apps=[APPLICATION_APP_NAME, MONGOS_APP_NAME],
        status="active",
        timeout=1000,
    )

    # prepare sharded cluster
    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(
        ops_test, mongos_unit, app_name=APPLICATION_APP_NAME, auth=True
    )
    assert mongos_running, "Mongos is not currently running."


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_mongos_stops_without_config_server(ops_test: OpsTest) -> None:
    """Tests that mongos powers down when no config server is accessible."""
    await ops_test.model.applications[CONFIG_SERVER_APP_NAME].remove_relation(
        f"{MONGOS_APP_NAME}:{CLUSTER_REL_NAME}",
        f"{CONFIG_SERVER_APP_NAME}:{CLUSTER_REL_NAME}",
    )

    await ops_test.model.wait_for_idle(
        apps=[
            APPLICATION_APP_NAME,
            MONGOS_APP_NAME,
            SHARD_APP_NAME,
            CONFIG_SERVER_APP_NAME,
        ],
        idle_period=10,
        raise_on_blocked=False,
    )

    mongos_unit = ops_test.model.applications[MONGOS_APP_NAME].units[0]
    mongos_running = await check_mongos(
        ops_test, mongos_unit, app_name=APPLICATION_APP_NAME, auth=False
    )
    assert not mongos_running, "Mongos is running without a config server."

    secrets = await get_application_relation_data(
        ops_test, "application", "mongos", "secret-user"
    )
    assert (
        secrets is None
    ), "mongos still has connection info without being connected to cluster."

    # verify that Charmed Mongos is blocked waiting for config-server
    await wait_for_mongos_units_blocked(
        ops_test,
        MONGOS_APP_NAME,
        status="Missing relation to config-server.",
        timeout=300,
    )
