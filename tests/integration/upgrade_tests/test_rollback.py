#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
import pathlib
import logging
import time
import pytest
import pytest_asyncio
import shutil
import zipfile
import re
import tenacity
from pytest_operator.plugin import OpsTest
from ..helpers import (
    APPLICATION_APP_NAME,
    check_mongos,
    deploy_cluster_components,
    get_juju_status,
    integrate_cluster_components,
    MONGOS_APP_NAME,
    run_mongos_command,
)

logger = logging.getLogger(__name__)

UPGRADE_TIMEOUT = 15 * 60


@pytest_asyncio.fixture
async def local_charm(ops_test: OpsTest):
    """Builds the regular charm."""
    charm = await ops_test.build_charm(".")
    yield charm


@pytest_asyncio.fixture
def faulty_upgrade_charm(local_charm, tmp_path: pathlib.Path):
    """Builds a faulty charm from the local charm.

    This works by modifying both the workload major version and the snap revision.
    This allows to test the detection of incompatible versions and test for rollbacks.
    """
    fault_charm = tmp_path / "fault_charm.charm"
    shutil.copy(local_charm, fault_charm)
    config_file = pathlib.Path("src/config.py")
    workload_version = pathlib.Path("workload_version").read_text().strip()

    [major, minor, patch] = workload_version.split(".")

    regex = re.compile(r"SNAP_PACKAGES.*\(.*, ([0-9]+)\)]")
    file_data = config_file.read_text().split("\n")
    for index, line in enumerate(file_data):
        if entry := regex.findall(line):
            current_rev = entry[0]
            new_rev = int(entry[0]) - 1
            new_line = line.replace(current_rev, str(new_rev))
            file_data[index] = new_line
            break

    with zipfile.ZipFile(fault_charm, mode="a") as charm_zip:
        charm_zip.writestr("src/config.py", "\n".join(file_data))
        charm_zip.writestr(
            "workload_version", f"{int(major) -1}.{minor}.{patch}+testrollback"
        )

    yield fault_charm


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest) -> None:
    """Build and deploy a sharded cluster."""
    await deploy_cluster_components(ops_test)
    await integrate_cluster_components(ops_test)


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_failed_upgrade_and_rollback(
    ops_test: OpsTest, local_charm: pathlib.Path, faulty_upgrade_charm: pathlib.Path
) -> None:
    """Tests that upgrade can be ran successfully."""
    mongos_application = ops_test.model.applications[MONGOS_APP_NAME]
    await mongos_application.refresh(path=faulty_upgrade_charm)
    logger.info("Wait for upgrade to fail")
    for attempt in tenacity.Retrying(
        reraise=True,
        stop=tenacity.stop_after_delay(UPGRADE_TIMEOUT),
        wait=tenacity.wait_fixed(10),
    ):
        with attempt:
            assert "Upgrade incompatible" in get_juju_status(
                ops_test.model.name, MONGOS_APP_NAME
            ), "Not indicating charm incompatible"

    logger.info("Re-refresh the charm")
    await mongos_application.refresh(path=local_charm)

    # sleep to ensure that active status from before re-refresh does not affect below check
    time.sleep(15)
    await ops_test.model.block_until(
        lambda: all(
            unit.workload_status == "active" for unit in mongos_application.units
        )
        and all(unit.agent_status == "idle" for unit in mongos_application.units)
    )

    logger.info("Wait for the charm to be rolled back")
    await ops_test.model.wait_for_idle(
        apps=[MONGOS_APP_NAME],
        status="active",
        timeout=1000,
        idle_period=30,
    )

    for unit in mongos_application.units:
        number = unit.name.split("/")[-1]
        cmd = f"db.test_collection.insertOne({{number: {number}}} );"
        return_code, _, std_err = await run_mongos_command(
            ops_test, unit, cmd, app_name=APPLICATION_APP_NAME
        )
        assert return_code == 0, f"mongos user failed to write data, error: {std_err}"
