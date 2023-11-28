# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

from charms.operator_libs_linux.v1 import snap
from ops.model import BlockedStatus
from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get


class TestCharm(unittest.TestCase):
    def setUp(self, *unused):
        self.harness = Harness(MongosOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
        self.peer_rel_id = self.harness.add_relation("router-peers", "router-peers")

    @patch_network_get(private_address="1.1.1.1")
    @patch("charm.snap.SnapCache")
    @patch("subprocess.check_call")
    def test_install_snap_packages_failure(self, _call, snap_cache):
        """Test verifies that install hook fails when a snap error occurs."""
        snap_cache.side_effect = snap.SnapError
        self.harness.charm.on.install.emit()
        self.assertTrue(isinstance(self.harness.charm.unit.status, BlockedStatus))
