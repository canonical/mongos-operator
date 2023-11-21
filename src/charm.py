#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from typing import Set
from charms.mongodb.v1.mongos import MongosConfiguration
from charms.mongodb.v0.mongodb import MongoDBConfiguration
from charms.mongodb.v1.helpers import copy_licenses_to_unit, get_mongos_args
from charms.mongodb.v1.users import (
    MongoDBUser,
    OperatorUser,
)
from charms.operator_libs_linux.v1 import snap

from config import Config
from machine_helpers import add_args_to_env

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
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.update_status, self._on_update_status)

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

        # Construct the mongod startup commandline args for systemd and reload the daemon.
        mongos_start_args = get_mongos_args(self.mongos_config, snap_install=True)
        add_args_to_env("MONGOS_ARGS", mongos_start_args)

        # add licenses
        copy_licenses_to_unit()

    @property
    def mongos_config(self) -> MongoDBConfiguration:
        """Generates a MongoDBConfiguration object for mongos in the deployment of MongoDB."""
        return self._get_mongos_config_for_user(OperatorUser, set(self._unit_ips))

    def _get_mongos_config_for_user(
        self, user: MongoDBUser, hosts: Set[str]
    ) -> MongosConfiguration:
        external_ca, _ = self.tls.get_tls_files(UNIT_SCOPE)
        internal_ca, _ = self.tls.get_tls_files(APP_SCOPE)

        return MongosConfiguration(
            database=user.get_database_name(),
            username=user.get_username(),
            password=self.get_secret(APP_SCOPE, user.get_password_key_name()),
            hosts=hosts,
            port=Config.MONGOS_PORT,
            roles=user.get_roles(),
            tls_external=external_ca is not None,
            tls_internal=internal_ca is not None,
        )
