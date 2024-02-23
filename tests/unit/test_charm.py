# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch


import pytest
import re
import json
from parameterized import parameterized
from unittest import mock


from charms.operator_libs_linux.v1 import snap
from ops.model import BlockedStatus, WaitingStatus
from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequiresEvents

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

        self.harness = Harness(MongosOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_rel_id = self.harness.add_relation("router-peers", "router-peers")

    @pytest.fixture
    def use_caplog(self, caplog):
        self._caplog = caplog

    @patch_network_get(private_address="1.1.1.1")
    @patch("charm.snap.SnapCache")
    @patch("subprocess.check_call")
    def test_install_snap_packages_failure(self, _call, snap_cache):
        """Test verifies that install hook fails when a snap error occurs."""
        snap_cache.side_effect = snap.SnapError
        self.harness.charm.on.install.emit()
        self.assertTrue(isinstance(self.harness.charm.unit.status, BlockedStatus))

    @parameterized.expand([("app"), ("unit")])
    def test_set_secret_returning_secret_id(self, scope):
        secret_id = self.harness.charm.set_secret(scope, "somekey", "bla")
        assert re.match(f"mongos.{scope}", secret_id)

    @parameterized.expand([("app"), ("unit")])
    def test_set_reset_new_secret(self, scope):
        self.harness.set_leader(True)

        # Getting current password
        self.harness.charm.set_secret(scope, "new-secret", "bla")
        assert self.harness.charm.get_secret(scope, "new-secret") == "bla"

        # Reset new secret
        self.harness.charm.set_secret(scope, "new-secret", "blablabla")
        assert self.harness.charm.get_secret(scope, "new-secret") == "blablabla"

        # Set another new secret
        self.harness.charm.set_secret(scope, "new-secret2", "blablabla")
        assert self.harness.charm.get_secret(scope, "new-secret2") == "blablabla"

    @parameterized.expand([("app"), ("unit")])
    def test_invalid_secret(self, scope):
        with self.assertRaises(TypeError):
            self.harness.charm.set_secret("unit", "somekey", 1)

        self.harness.charm.set_secret("unit", "somekey", "")
        assert self.harness.charm.get_secret(scope, "somekey") is None

    @patch("charm.MongosOperatorCharm.get_secret", return_value=None)
    def test_get_keyfile_contents_no_secret(self, get_secret):
        """Tests file isn't checked if secret isn't set."""
        self.assertEqual(self.harness.charm.get_keyfile_contents(), None)

    @patch("charm.MongosOperatorCharm.get_secret", return_value="keyfile-contents")
    @patch("charm.Path")
    def test_get_keyfile_contents_no_keyfile(self, path, get_secret):
        """Tests file isn't checked if file doesn't exists."""
        path_function = mock.Mock()
        path_function.is_file.return_value = False
        path.return_value = path_function
        self.assertEqual(self.harness.charm.get_keyfile_contents(), None)

    def test_proceed_on_broken_event(self):
        """Tests that proceed on broken event only returns true when relation is broken.

        Note: relation broken events also occur when scaling down related applications so it is
        important to differentiate the two."""

        # case 1: no relation departed check has run
        mock_event = mock.Mock()
        mock_event.event.relation.id = 7
        assert not self.harness.charm.proceed_on_broken_event(mock_event)
        mock_event.defer.assert_called()

        # case 2: relation departed check ran, but is due to scale down
        mock_event = mock.Mock()
        mock_event.relation.id = 7
        self.harness.charm.unit_peer_data[
            self.harness.charm._generate_relation_departed_key("7")
        ] = json.dumps(True)
        assert not self.harness.charm.proceed_on_broken_event(mock_event)
        mock_event.defer.assert_not_called()

        # case 3: relation departed check ran and is due to a broken event
        mock_event = mock.Mock()
        mock_event.relation.id = 7
        self.harness.charm.unit_peer_data[
            self.harness.charm._generate_relation_departed_key("7")
        ] = json.dumps(False)
        assert self.harness.charm.proceed_on_broken_event(mock_event)
        mock_event.defer.assert_not_called()

    def test_status_shows_mongos_waiting(self):
        """Tests when mongos accurately reports waiting status."""
        cluster_mock = mock.Mock()
        cluster_mock.is_mongos_running.return_value = False
        self.harness.charm.cluster = cluster_mock

        # A running config server is a requirement to start for mongos
        self.harness.charm.on.update_status.emit()
        self.assertTrue(isinstance(self.harness.charm.unit.status, BlockedStatus))

        self.harness.add_relation("cluster", "config-server")
        self.harness.charm.on.update_status.emit()
        self.assertTrue(isinstance(self.harness.charm.unit.status, WaitingStatus))

    @patch_network_get(private_address="1.1.1.1")
    def test_mongos_host(self):
        """TBD."""
        self.harness.charm.app_peer_data["external-connectivity"] = json.dumps(False)
        mongos_host = self.harness.charm.get_mongos_host()
        self.assertEqual(mongos_host, MONGOS_SOCKET_URI_FMT)

        self.harness.charm.app_peer_data["external-connectivity"] = json.dumps(True)
        mongos_host = self.harness.charm.get_mongos_host()
        self.assertEqual(mongos_host, "1.1.1.1")
