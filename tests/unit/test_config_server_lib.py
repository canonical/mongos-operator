# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import unittest
from unittest.mock import patch

from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get


PEER_ADDR = {"private-address": "127.4.5.6"}
KEYFILE = {"key-file": "key-file-contents"}


class TestConfigServerInterface(unittest.TestCase):
    @patch_network_get(private_address="1.1.1.1")
    def setUp(self):
        self.harness = Harness(MongosOperatorCharm)
        self.harness.begin()
        self.harness.add_relation("router-peers", "router-peers")
        self.harness.set_leader(True)
        self.charm = self.harness.charm
        self.addCleanup(self.harness.cleanup)

    @patch("ops.framework.EventBase.defer")
    @patch("charm.ClusterRequirer.update_keyfile")
    def test_on_relation_changed_waits_keyfile(self, update_keyfile, defer):
        """Tests that relation changed waits for keyfile."""

        # fails due to being run on non-config-server
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server/0", PEER_ADDR)
        update_keyfile.assert_not_called()
        defer.assert_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    def test_same_keyfile(self, set_secret, get_keyfile_contents, push_file_to_unit):
        """Tests that charm doesn't update keyfile when they are the same."""
        get_keyfile_contents.return_value = KEYFILE["key-file"]
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", KEYFILE)

        push_file_to_unit.assert_not_called()
        set_secret.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    def test_non_leader_doesnt_set_keyfile_secret(
        self, set_secret, get_keyfile_contents, push_file_to_unit
    ):
        """Tests that non leaders dont set keyfile secret."""
        self.harness.set_leader(False)

        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", KEYFILE)

        push_file_to_unit.assert_called()
        set_secret.assert_not_called()
