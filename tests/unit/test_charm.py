# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch


import pytest
from parameterized import parameterized
from unittest import mock

from ops.testing import Harness

from charm import MongosVMCharm


from single_kernel_mongo.lib.charms.data_platform_libs.v0.data_interfaces import (
    DatabaseRequiresEvents,
)
from single_kernel_mongo.config.literals import Scope
from single_kernel_mongo.exceptions import (
    DeferrableFailedHookChecksError,
    NonDeferrableFailedHookChecksError,
    WorkloadNotReadyError,
)

CLUSTER_ALIAS = "cluster"
MONGOS_SOCKET_URI_FMT = (
    "%2Fvar%2Fsnap%2Fcharmed-mongodb%2Fcommon%2Fvar%2Fmongodb-27018.sock"
)


class TestCharm(unittest.TestCase):
    def setUp(self, *unused):
        try:
            # runs before each test to delete the custom events created for the aliases. This is
            # needed because the events are created again in the next test, which causes an error
            # related to duplicated events.
            delattr(DatabaseRequiresEvents, f"{CLUSTER_ALIAS}_database_created")
            delattr(DatabaseRequiresEvents, f"{CLUSTER_ALIAS}_endpoints_changed")
            delattr(
                DatabaseRequiresEvents, f"{CLUSTER_ALIAS}_read_only_endpoints_changed"
            )
        except AttributeError:
            # Ignore the events not existing before the first test.
            pass

        self.harness = Harness(MongosVMCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_rel_id = self.harness.add_relation("router-peers", "router-peers")
        self.peer_rel_id = self.harness.add_relation(
            "upgrade-version-a", "upgrade-version-a"
        )
        self.status_peer_rel_id = self.harness.add_relation("status-peers", "mongos")

    @pytest.fixture
    def use_caplog(self, caplog):
        self._caplog = caplog

    @pytest.fixture(autouse=True)
    def tenacity_wait(self, mocker):
        mocker.patch("tenacity.nap.time")

    def test_install_snap_packages_failure(self):
        """Test verifies that install hook fails when a snap error occurs."""
        with (
            patch(
                "single_kernel_mongo.core.vm_workload.VMWorkload.install",
                return_value=False,
            ),
            pytest.raises(WorkloadNotReadyError),
        ):
            self.harness.charm.on.install.emit()

    @parameterized.expand([(Scope.APP), (Scope.UNIT)])
    def test_invalid_secret(self, scope):
        with self.assertRaises(TypeError):
            self.harness.charm.operator.state.secrets.set("somekey", 1, Scope.UNIT)

        self.harness.charm.operator.state.secrets.remove(Scope.UNIT, "somekey")
        assert (
            self.harness.charm.operator.state.secrets.get_for_key(scope, "somekey")
            is None
        )

    def test_get_keyfile_contents_no_secret(self):
        """Tests file isn't checked if secret isn't set."""
        self.assertEqual(self.harness.charm.operator.state.get_keyfile(), None)

    def test_proceed_on_broken_event(self):
        """Tests that proceed on broken event only returns true when relation is broken.

        Note: relation broken events also occur when scaling down related applications so it is
        important to differentiate the two."""

        # case 1: no relation departed check has run
        mock_relation = mock.Mock()
        mock_relation.id = 7
        with self.assertRaises(DeferrableFailedHookChecksError):
            assert not self.harness.charm.operator.assert_proceed_on_broken_event(
                mock_relation
            )

        # case 2: relation departed check ran, but is due to scale down
        mock_relation = mock.Mock()
        mock_relation.id = 7
        self.harness.charm.operator.state.set_scaling_down(
            mock_relation.id, self.harness._unit_name
        )
        with self.assertRaises(NonDeferrableFailedHookChecksError):
            self.harness.charm.operator.assert_proceed_on_broken_event(mock_relation)

        # case 3: relation departed check ran and is due to a broken event
        mock_relation = mock.Mock()
        mock_relation.id = 7
        self.harness.charm.operator.state.set_scaling_down(mock_relation.id, "other")
        self.harness.charm.operator.assert_proceed_on_broken_event(mock_relation)

    @pytest.mark.usefixtures("mock_fs_interactions")
    def test_status_shows_mongos_waiting(self):
        """Tests when mongos accurately reports waiting status."""
        mock_mongos_running = mock.Mock()
        mock_mongos_running.return_value = False
        mock_cluster = mock.Mock()
        mock_cluster.get_tls_statuses.return_value = None
        self.harness.charm.operator.is_mongos_running = mock_mongos_running
        self.harness.charm.operator.cluster_manager = mock_cluster

        # A running config server is a requirement to start for mongos
        self.harness.charm.on.update_status.emit()

        statuses = self.harness.charm.operator.state.statuses.get(
            scope="unit", component=self.harness.charm.operator.name
        )

        self.assertTrue(statuses[0].status == "blocked")

        self.harness.add_relation("cluster", "config-server")
        self.harness.charm.on.update_status.emit()

        statuses = self.harness.charm.operator.state.statuses.get(
            scope="unit", component=self.harness.charm.operator.name
        )

        self.assertTrue(statuses[0].status == "waiting")

    def test_mongos_host(self):
        """TBD."""
        self.harness.set_leader(True)
        self.harness.charm.operator.state.app_peer_data.external_connectivity = False
        mongos_host = self.harness.charm.operator.state.app_hosts
        self.assertEqual(mongos_host, {MONGOS_SOCKET_URI_FMT})

        self.harness.charm.operator.state.app_peer_data.external_connectivity = True
        mongos_host = self.harness.charm.operator.state.app_hosts
        self.assertEqual(mongos_host, {"10.0.0.10"})
