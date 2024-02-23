# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import unittest

from unittest.mock import patch

from ops.testing import Harness

from charm import MongosOperatorCharm

from .helpers import patch_network_get

from charms.data_platform_libs.v0.data_interfaces import DatabaseRequiresEvents

PEER_ADDR = {"private-address": "127.4.5.6"}
REL_DATA = {
    "database": "database",
    "extra-user-roles": "admin",
}
EXTERNAL_CONNECTIVITY_TAG = "external-node-connectivity"

MONGOS_VAR = "MONGOS_ARGS=--configdb config-server-db/host:port"

CLUSTER_ALIAS = "cluster"


class TestMongosInterface(unittest.TestCase):
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

    @patch("charm.MongosOperatorCharm.open_mongos_port")
    def test_mongos_opens_port_external(self, open_mongos_port):
        """Tests that relation changed does not wait for keyfile.

        When mongos is incorrectly integrated with a non-config server (ie shard), it can end up
        waiting forever for a keyfile
        """
        # fails due to being run on non-config-server
        relation_id = self.harness.add_relation("mongos_proxy", "host-charm")
        self.harness.add_relation_unit(relation_id, "host-charm/0")
        self.harness.update_relation_data(relation_id, "host-charm", REL_DATA)
        open_mongos_port.assert_not_called()

        REL_DATA[EXTERNAL_CONNECTIVITY_TAG] = "true"
        self.harness.update_relation_data(relation_id, "host-charm", REL_DATA)
        open_mongos_port.assert_called()
