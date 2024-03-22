# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import unittest

from unittest.mock import patch, mock_open

from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequiresEvents

PEER_ADDR = {"private-address": "127.4.5.6"}
REL_DATA = {
    "key-file": "key-file-contents",
    "config-server-db": "config-server-db/host:port",
}
MONGOS_VAR = "MONGOS_ARGS=--configdb config-server-db/host:port"

CLUSTER_ALIAS = "cluster"


class TestConfigServerInterface(unittest.TestCase):
    @patch_network_get(private_address="1.1.1.1")
    def setUp(self):
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
        self.harness.begin()
        self.harness.add_relation("router-peers", "router-peers")
        self.harness.set_leader(True)
        self.charm = self.harness.charm
        self.addCleanup(self.harness.cleanup)

    @patch("ops.framework.EventBase.defer")
    @patch("charm.ClusterRequirer.update_keyfile")
    def test_on_relation_changed_waits_keyfile(self, update_keyfile, defer):
        """Tests that relation changed does not wait for keyfile.

        When mongos is incorrectly integrated with a non-config server (ie shard), it can end up
        waiting forever for a keyfile
        """

        # fails due to being run on non-config-server
        relation_id = self.harness.add_relation("cluster", "shard")
        self.harness.add_relation_unit(relation_id, "shard/0")
        self.harness.update_relation_data(relation_id, "shard/0", PEER_ADDR)
        update_keyfile.assert_not_called()
        defer.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    @patch("charm.ClusterRequirer.update_config_server_db")
    @patch("charm.ClusterRequirer.is_mongos_running")
    @patch("charm.MongosOperatorCharm.restart_charm_services")
    def test_same_keyfile(
        self,
        restart_charm_services,
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
    @patch("charm.MongosOperatorCharm.restart_charm_services")
    def test_non_leader_doesnt_set_keyfile_secret(
        self,
        restart_charm_services,
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
    @patch("charm.MongosOperatorCharm.restart_charm_services")
    @patch("charms.mongodb.v0.config_server_interface.add_args_to_env")
    @patch("builtins.open", new_callable=mock_open, read_data=MONGOS_VAR)
    @patch("charm.Path")
    def test_same_config_db(
        self,
        path,
        open,
        add_args_to_env,
        restart_charm_services,
        is_mongos_running,
        set_secret,
        get_keyfile_contents,
        push_file_to_unit,
    ):
        """Tests that charm doesn't update config-server when they are the same."""
        get_keyfile_contents.return_value = REL_DATA["key-file"]

        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)

        add_args_to_env.assert_not_called()

    @patch("charm.MongosOperatorCharm.push_file_to_unit")
    @patch("charm.MongosOperatorCharm.get_keyfile_contents")
    @patch("charm.MongosOperatorCharm.set_secret")
    @patch("charm.ClusterRequirer.is_mongos_running", return_value=False)
    @patch("ops.framework.EventBase.defer")
    @patch("charm.MongosOperatorCharm.restart_charm_services")
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

    @patch("charm.ClusterRequirer._on_relation_changed")
    @patch("charm.MongosOperatorCharm.has_departed_run")
    @patch("charm.MongosOperatorCharm.proceed_on_broken_event")
    @patch("charm.MongosOperatorCharm.stop_mongos_service")
    def test_broken_does_not_excute_on_scale_down(
        self,
        stop_mongos_service,
        has_departed_run,
        proceed_on_broken_event,
        rel_changed,
    ):
        # case 1: scale down check has not run yet
        has_departed_run.return_value = False
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        self.harness.remove_relation(relation_id)
        stop_mongos_service.assert_not_called()

        # case 2: broken event is due to scale down
        has_departed_run.return_value = True
        proceed_on_broken_event.return_value = False
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        self.harness.remove_relation(relation_id)
        stop_mongos_service.assert_not_called()

    @patch("charm.ClusterRequirer._on_relation_changed")
    @patch("charm.MongosOperatorCharm.remove_connection_info")
    @patch("charm.MongosOperatorCharm.has_departed_run")
    @patch("charm.MongosOperatorCharm.proceed_on_broken_event")
    @patch("charm.MongosOperatorCharm.stop_mongos_service")
    def test_broken_stops_mongos(
        self,
        stop_mongos_service,
        has_departed_run,
        proceed_on_broken_event,
        remove_connection_info,
        rel_changed,
    ):
        """When the relation to config-server is broken all units should stop mongos service."""
        # case 1: non-leader units stop mongos
        has_departed_run.return_value = True
        proceed_on_broken_event.return_value = True
        self.harness.set_leader(False)
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        self.harness.remove_relation(relation_id)
        stop_mongos_service.assert_called()
        # despite stopping the mongos service, only leaders should remove connection info.
        remove_connection_info.assert_not_called()

        # case 2: leader units stop mongos
        has_departed_run.return_value = True
        proceed_on_broken_event.return_value = True
        self.harness.set_leader(True)
        relation_id = self.harness.add_relation("cluster", "config-server")
        self.harness.add_relation_unit(relation_id, "config-server/0")
        self.harness.update_relation_data(relation_id, "config-server", REL_DATA)
        self.harness.remove_relation(relation_id)
        stop_mongos_service.assert_called()
        # leaders should remove the connection info.
        remove_connection_info.assert_called()
