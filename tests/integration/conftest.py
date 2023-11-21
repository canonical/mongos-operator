#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import pytest
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
async def application_charm(ops_test: OpsTest):
    """Build the application charm."""
    charm_path = "tests/integration/application"
    charm = await ops_test.build_charm(charm_path)
    return charm


@pytest.fixture(scope="module")
async def mongos_charm(ops_test: OpsTest):
    """Build the mongos charm."""
    charm = await ops_test.build_charm(".")
    return charm
