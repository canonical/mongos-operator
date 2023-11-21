#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from typing import List
from charms.mongodb.v0.mongodb_secrets import SecretCache
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

        self.secrets = SecretCache(self)

    # START: hook functions
    def _on_install(self, event: InstallEvent) -> None:
        """Handle the install event (fired on startup)."""
        self.unit.status = MaintenanceStatus("installing mongos")
        try:
            self._install_snap_packages(packages=Config.SNAP_PACKAGES)

        except snap.SnapError:
            self.unit.status = BlockedStatus("couldn't install mongos")
            return

        # clear the default config file - user provided config files will be added in the config
        # changed hook
        try:
            with open(Config.MONGOD_CONF_FILE_PATH, "r+") as f:
                f.truncate(0)
        except IOError:
            self.unit.status = BlockedStatus("Could not install mongos")
            return

        # add licenses
        copy_licenses_to_unit()

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
                    "An exception occurred when installing %s. Reason: %s", snap_name, str(e)
                )
                raise

    # END: helper functions


if __name__ == "__main__":
    ops.main(MongosOperatorCharm)
