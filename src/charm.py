#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
from typing import List
import os
import pwd
from charms.mongodb.v1.helpers import copy_licenses_to_unit, KEY_FILE
from charms.operator_libs_linux.v1 import snap
from pathlib import Path

from charms.mongodb.v0.mongodb_secrets import SecretCache
from typing import Set, List, Optional
from exceptions import ApplicationHostNotFoundError
from charms.mongodb.v0.mongodb_secrets import generate_secret_label
from charms.mongodb.v1.mongos import MongosConfiguration
from charms.mongodb.v0.mongodb import MongoDBConfiguration
from charms.mongodb.v1.helpers import copy_licenses_to_unit
from charms.mongodb.v0.config_server_interface import ClusterRequirer
from charms.mongodb.v1.users import (
    MongoDBUser,
    OperatorUser,
)

from config import Config

import ops
from ops.model import BlockedStatus, MaintenanceStatus, Unit, Relation
from ops.charm import (
    InstallEvent,
    StartEvent,
)

import logging


logger = logging.getLogger(__name__)

APP_SCOPE = Config.Relations.APP_SCOPE
UNIT_SCOPE = Config.Relations.UNIT_SCOPE
ROOT_USER_GID = 0
MONGO_USER = "snap_daemon"


class MongosOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)

        self.cluster = ClusterRequirer(self)
        self.secrets = SecretCache(self)
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
                    "An exception occurred when installing %s. Reason: %s", snap_name, str(e)
                )
                raise

    @property
    def mongos_config(self) -> MongoDBConfiguration:
        """Generates a MongoDBConfiguration object for mongos in the deployment of MongoDB."""
        return self._get_mongos_config_for_user(OperatorUser, set(self._unit_ips))

    def _get_mongos_config_for_user(
        self, user: MongoDBUser, hosts: Set[str], config_server_uri: str
    ) -> MongosConfiguration:

        return MongosConfiguration(
            config_server_uri=config_server_uri,
            database=user.get_database_name(),
            username=user.get_username(),
            password=self.get_secret(APP_SCOPE, user.get_password_key_name()),
            hosts=hosts,
            port=Config.MONGOS_PORT,
            roles=user.get_roles(),
            tls_external=None,  # Future PR will suport TLS
            tls_internal=None,  # Future PR will suport TLS
        )

    def _unit_ip(self, unit: Unit) -> str:
        """Returns the ip address of a given unit."""
        # check if host is current host
        if unit == self.unit:
            return str(self.model.get_binding(Config.Relations.PEERS).network.bind_address)
        # check if host is a peer
        elif unit in self._peers.data:
            return str(self._peers.data[unit].get("private-address"))
        # raise exception if host not found
        else:
            raise ApplicationHostNotFoundError

    @property
    def _unit_ips(self) -> List[str]:
        """Retrieve IP addresses associated with MongoDB application.

        Returns:
            a list of IP address associated with MongoDB application.
        """
        peer_addresses = []
        if self._peers:
            peer_addresses = [self._unit_ip(unit) for unit in self._peers.units]

        self_address = self._unit_ip(self.unit)
        addresses = []
        if peer_addresses:
            addresses.extend(peer_addresses)
        addresses.append(self_address)
        return addresses

    @property
    def _peers(self) -> Optional[Relation]:
        """Fetch the peer relation.

        Returns:
             An `ops.model.Relation` object representing the peer relation.
        """
        return self.model.get_relation(Config.Relations.PEERS)

    def get_secret(self, scope: str, key: str) -> Optional[str]:
        """Get secret from the secret storage."""
        label = generate_secret_label(self, scope)
        secret = self.secrets.get(label)
        if not secret:
            return

        value = secret.get_content().get(key)
        if value != Config.Secrets.SECRET_DELETED_LABEL:
            return value

    def set_secret(self, scope: str, key: str, value: Optional[str]) -> Optional[str]:
        """Set secret in the secret storage.

        Juju versions > 3.0 use `juju secrets`, this function first checks
          which secret store is being used before setting the secret.
        """
        if not value:
            return self.remove_secret(scope, key)

        label = generate_secret_label(self, scope)
        secret = self.secrets.get(label)
        if not secret:
            self.secrets.add(label, {key: value}, scope)
        else:
            content = secret.get_content()
            content.update({key: value})
            secret.set_content(content)
        return label

    def remove_secret(self, scope, key) -> None:
        """Removing a secret."""
        label = generate_secret_label(self, scope)
        secret = self.secrets.get(label)

        if not secret:
            return

        content = secret.get_content()

        if not content.get(key) or content[key] == Config.Secrets.SECRET_DELETED_LABEL:
            logger.error(f"Non-existing secret {scope}:{key} was attempted to be removed.")
            return

        content[key] = Config.Secrets.SECRET_DELETED_LABEL
        secret.set_content(content)

    def get_keyfile_contents(self) -> str:
        """Retrieves the contents of the keyfile on host machine."""
        # wait for keyFile to be created by leader unit
        if not self.get_secret(APP_SCOPE, Config.Secrets.SECRET_KEYFILE_NAME):
            logger.debug("waiting for leader unit to generate keyfile contents")
            return

        key_file_path = f"{Config.MONGOD_CONF_DIR}/{KEY_FILE}"
        key_file = Path(key_file_path)
        if not key_file.is_file():
            logger.info("no keyfile present")
            return

        with open(key_file_path, "r") as file:
            key = file.read()

        return key

    def push_file_to_unit(self, parent_dir, file_name, file_contents) -> None:
        """K8s charms can push files to their containers easily, this is a vm charm workaround."""
        Path(parent_dir).mkdir(parents=True, exist_ok=True)
        file_name = f"{parent_dir}/{file_name}"
        with open(file_name, "w") as write_file:
            write_file.write(file_contents)

        # MongoDB limitation; it is needed 400 rights for keyfile and we need 440 rights on tls
        # certs to be able to connect via MongoDB shell
        if Config.TLS.KEY_FILE_NAME in file_name:
            os.chmod(file_name, 0o400)
        else:
            os.chmod(file_name, 0o440)
        mongodb_user = pwd.getpwnam(MONGO_USER)
        os.chown(file_name, mongodb_user.pw_uid, ROOT_USER_GID)

    # END: helper functions


if __name__ == "__main__":
    ops.main(MongosOperatorCharm)
