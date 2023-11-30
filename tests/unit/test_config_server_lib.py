# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import unittest
import json

from unittest.mock import patch

from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get


PEER_ADDR = {"private-address": "127.4.5.6"}
REL_DATA = {
    "key-file": "key-file-contents",
    "config-server-db": "config-server-db/host:port",
}


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
    @patch("charm.ClusterRequirer.update_config_server_db")
    @patch("charm.ClusterRequirer.is_mongos_running")
    @patch("charm.MongosOperatorCharm.restart_mongos_service")
    def test_same_keyfile(
        self,
        restart_mongos_service,
        is_mongos_running,
        update_config_server_db,
        set_secret,
        get_keyfile_contents,
        push_file_to_unit,
    ):
        """Tests that charm doesn't update keyfile when they are the same."""
        get_keyfile_contents.return_value = REL_DATA["key-file"]
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)

        push_file_to_unit.assert_not_called()
        set_secret.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    @patch("charm.ClusterRequirer.update_config_server_db", return_value=False)
    @patch("charm.ClusterRequirer.is_mongos_running")
    @patch("charm.MongosOperatorCharm.restart_mongos_service")
    def test_non_leader_doesnt_set_keyfile_secret(
        self,
        restart_mongos_service,
        is_mongos_running,
        update_config_server_db,
        set_secret,
        get_keyfile_contents,
        push_file_to_unit,
    ):
        """Tests that non leaders dont set keyfile secret."""
        self.harness.set_leader(False)

        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)

        push_file_to_unit.assert_called()
        set_secret.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    @patch("charm.ClusterRequirer.is_mongos_running")
    @patch("charm.MongosOperatorCharm.restart_mongos_service")
    @patch("charms.mongodb.v0.config_server_interface.add_args_to_env")
    def test_same_config_db(
        self,
        add_args_to_env,
        restart_mongos_service,
        is_mongos_running,
        set_secret,
        get_keyfile_contents,
        push_file_to_unit,
    ):
        """Tests that charm doesn't update config-server when they are the same."""
        get_keyfile_contents.return_value = REL_DATA["key-file"]
        self.harness.charm.unit_peer_data["config_server_db"] = json.dumps(
            "config-server-db/host:port"
        )
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)

        add_args_to_env.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    @patch("charm.ClusterRequirer.is_mongos_running", return_value=False)
    @patch("ops.framework.EventBase.defer")
    @patch("charm.MongosOperatorCharm.restart_mongos_service")
    def retry_restart_mongos(
        self,
        restart_mongos,
        defer,
        is_mongos_running,
        set_secret,
        get_keyfile_contents,
        push_file_to_unit,
    ):
        """Tests that when the charm failed to start mongos it tries again."""
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        restart_mongos.assert_called()
        defer.assert_called()

        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")

        # update with the same data
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        restart_mongos.assert_called()
