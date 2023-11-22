#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from typing import List
from charms.mongodb.v1.helpers import copy_licenses_to_unit
from charms.operator_libs_linux.v1 import snap

from config import Config

import ops
from ops.model import (
    BlockedStatus,
    MaintenanceStatus,
)
from ops.charm import (
    InstallEvent,
    StartEvent,
)

import logging


logger = logging.getLogger(__name__)

APP_SCOPE = Config.Relations.APP_SCOPE
UNIT_SCOPE = Config.Relations.UNIT_SCOPE


class MongosOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)

        # todo future PRs:
        # 1. start daemon when relation to config server is made
        # 2. add users for related application
        # 3. update status indicates missing relations

    # BEGIN: hook functions
    def _on_install(self, event: InstallEvent) -> None:
        """Handle the install event (fired on startup)."""
        self.unit.status = MaintenanceStatus("installing mongos")
        try:
            self._install_snap_packages(packages=Config.SNAP_PACKAGES)

        except snap.SnapError as e:
            logger.info("Failed to install snap, error: %s", e)
            self.unit.status = BlockedStatus("couldn't install mongos")
            return

        # add licenses
        copy_licenses_to_unit()

    def _on_start(self, event: StartEvent) -> None:
        """Handle the start event."""
        # start hooks are fired before relation hooks and `mongos` requires a config-server in
        # order to start. Wait to receive config-server info from the relation event before
        # starting `mongos` daemon
        self.unit.status = BlockedStatus("Missing relation to config-server.")

    # END: hook functions

    # BEGIN: helper functions

    def _install_snap_packages(self, packages: List[str]) -> None:
        """Installs package(s) to container.

        Args:
            packages: list of packages to install.
        """
        for snap_name, snap_channel, snap_revision in packages:
            try:
                snap_cache = snap.SnapCache()
                snap_package = snap_cache[snap_name]
                snap_package.ensure(
                    snap.SnapState.Latest, channel=snap_channel, revision=snap_revision
                )
                # snaps will auto refresh so it is necessary to hold the current revision
                snap_package.hold()

            except snap.SnapError as e:
                logger.error(
                    "An exception occurred when installing %s. Reason: %s",
                    snap_name,
                    str(e),
                )
                raise

    # END: helper functions


if __name__ == "__main__":
    ops.main(MongosOperatorCharm)
