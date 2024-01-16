#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import os
import pwd
from charms.mongodb.v1.helpers import copy_licenses_to_unit, KEY_FILE
from charms.operator_libs_linux.v1 import snap
from pathlib import Path

from charms.mongodb.v0.mongodb_secrets import SecretCache
from charms.mongos.v0.mongos_client_interface import MongosProvider
from typing import Set, List, Optional, Dict
from charms.mongodb.v0.mongodb_secrets import generate_secret_label
from charms.mongodb.v1.mongos import MongosConfiguration
from charms.mongodb.v0.config_server_interface import ClusterRequirer
from charms.mongodb.v1.users import (
    MongoDBUser,
)

from config import Config

import ops
from ops.model import BlockedStatus, MaintenanceStatus, Relation
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
ENV_VAR_PATH = "/etc/environment"
MONGOS_VAR = "MONGOS_ARGS"
CONFIG_ARG = "--configdb"
USER_ROLES_TAG = "extra-user-roles"
DATABASE_TAG = "database"


class MongosOperatorCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)

        self.cluster = ClusterRequirer(self)
        self.secrets = SecretCache(self)
        self.mongos_provider = MongosProvider(self)
        # 1. add users for related application (to be done on config-server charm side)
        # 2. update status indicates missing relations

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

    def _get_mongos_config_for_user(
        self, user: MongoDBUser, hosts: Set[str]
    ) -> MongosConfiguration:
        return MongosConfiguration(
            database=user.get_database_name(),
            username=user.get_username(),
            password=self.get_secret(APP_SCOPE, user.get_password_key_name()),
            hosts=hosts,
            port=Config.MONGOS_PORT,
            roles=user.get_roles(),
            tls_external=None,  # Future PR will support TLS
            tls_internal=None,  # Future PR will support TLS
        )

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

    def start_mongos_service(self) -> None:
        """Starts the mongos service.

        Raises:
            snap.SnapError
        """
        snap_cache = snap.SnapCache()
        mongodb_snap = snap_cache["charmed-mongodb"]
        mongodb_snap.start(services=["mongos"], enable=True)

    def stop_mongos_service(self) -> None:
        """Stops the mongos service.

        Raises:
            snap.SnapError
        """
        snap_cache = snap.SnapCache()
        mongodb_snap = snap_cache["charmed-mongodb"]
        mongodb_snap.stop(services=["mongos"])

    def restart_mongos_service(self) -> None:
        """Retarts the mongos service.

        Raises:
            snap.SnapError
        """
        self.stop_mongos_service()
        self.start_mongos_service()

    def remove_connection_info(self) -> None:
        self.mongos_provider.remove_connection_info()

    def share_connection_info(self) -> None:
        """Future PR - generate URI and give it to related app"""

        self.mongos_provider.update_connection_info(self.mongos_config)

    def set_user_roles(self, roles: List[str]) -> None:
        """Updates the roles for the mongos user."""
        roles_str = ",".join(roles)
        self.app_peer_data[USER_ROLES_TAG] = roles_str

        if len(self.model.relations[Config.Relations.CLUSTER_RELATIONS_NAME]) == 0:
            return

        # a mongos shard can only be related to one config server
        config_server_rel = self.model.relations[Config.Relations.CLUSTER_RELATIONS_NAME][0]
        self.cluster.database_requires.update_relation_data(
            config_server_rel.id, {USER_ROLES_TAG: roles_str}
        )

    def set_database(self, database: str) -> None:
        """Updates the database requested for the mongos user."""
        self.app_peer_data[DATABASE_TAG] = database

        if len(self.model.relations[Config.Relations.CLUSTER_RELATIONS_NAME]) == 0:
            return

        # a mongos shard can only be related to one config server
        config_server_rel = self.model.relations[Config.Relations.CLUSTER_RELATIONS_NAME][0]
        self.cluster.database_requires.update_relation_data(
            config_server_rel.id, {DATABASE_TAG: database}
        )

    def check_relation_broken_or_scale_down(self, event: RelationDepartedEvent) -> None:
        """Checks relation departed event is the result of removed relation or scale down.

        Relation departed and relation broken events occur during scaling down or during relation
        removal, only relation departed events have access to metadata to determine which case.
        """
        scaling_down = self.set_scaling_down(event)

        if scaling_down:
            logger.info(
                "Scaling down the application, no need to process removed relation in broken hook."
            )

    def is_scaling_down(self, rel_id: int) -> bool:
        """Returns True if the application is scaling down."""
        rel_departed_key = self._generate_relation_departed_key(rel_id)
        return json.loads(self.unit_peer_data[rel_departed_key])

    def has_departed_run(self, rel_id: int) -> bool:
        """Returns True if the relation departed event has run."""
        rel_departed_key = self._generate_relation_departed_key(rel_id)
        return rel_departed_key in self.unit_peer_data

    def set_scaling_down(self, event: RelationDepartedEvent) -> bool:
        """Sets whether or not the current unit is scaling down."""
        # check if relation departed is due to current unit being removed. (i.e. scaling down the
        # application.)
        rel_departed_key = self._generate_relation_departed_key(event.relation.id)
        scaling_down = event.departing_unit == self.unit
        self.unit_peer_data[rel_departed_key] = json.dumps(scaling_down)
        return scaling_down

    def proceed_on_broken_event(self, event) -> bool:
        """Returns True if relation broken event should be acted on.."""
        # Only relation_deparated events can check if scaling down
        departed_relation_id = event.relation.id
        if not self.has_departed_run(departed_relation_id):
            logger.info(
                "Deferring, must wait for relation departed hook to decide if relation should be removed."
            )
            event.defer()
            return False

        # check if were scaling down and add a log message
        if self.is_scaling_down(departed_relation_id):
            logger.info(
                "Relation broken event occurring due to scale down, do not proceed to remove users."
            )
            return False

        return True

    @staticmethod
    def _generate_relation_departed_key(rel_id: int) -> str:
        """Generates the relation departed key for a specified relation id."""
        return f"relation_{rel_id}_departed"

    # END: helper functions

    # BEGIN: properties

    @property
    def database(self) -> Optional[str]:
        """Returns the database requested by the hosting application of the subordinate charm."""
        if not self._peers:
            logger.info("Peer relation not joined yet.")
            # TODO future PR implement relation interface between host application mongos and use
            # host application name in generation of db name.
            return "mongos-database"

        return self.app_peer_data.get(DATABASE_TAG, "mongos-database")

    @property
    def extra_user_roles(self) -> Set[str]:
        """Returns the user roles requested by the hosting application of the subordinate charm."""
        if not self._peers:
            logger.info("Peer relation not joined yet.")
            return None

        return self.app_peer_data.get(USER_ROLES_TAG, "default")

    @property
    def mongos_config(self) -> MongosConfiguration:
        """Generates a MongoDBConfiguration object for mongos in the deployment of MongoDB."""
        # TODO future PR - use ip addresses for hosts for data-integrator as that charm will not
        # communicate to mongos via the Unix Domain Socket.
        hosts = [Config.MONGOS_SOCKET_URI_FMT]
        # mongos using Unix Domain Socket to communicate do not use port, Future PR - use port
        # when suborinate charm of data-integrator.
        port = None

        return MongosConfiguration(
            database=self.database,
            username=self.get_secret(APP_SCOPE, Config.Secrets.USERNAME),
            password=self.get_secret(APP_SCOPE, Config.Secrets.PASSWORD),
            hosts=hosts,
            port=port,
            roles=self.extra_user_roles,
            tls_external=None,  # Future PR will support TLS
            tls_internal=None,  # Future PR will support TLS
        )

    @property
    def _peers(self) -> Optional[Relation]:
        """Fetch the peer relation.

        Returns:
             An `ops.model.Relation` object representing the peer relation.
        """
        return self.model.get_relation(Config.Relations.PEERS)

    @property
    def _peers(self) -> Optional[Relation]:
        """Fetch the peer relation.

        Returns:
             An `ops.model.Relation` object representing the peer relation.
        """
        return self.model.get_relation(Config.Relations.PEERS)

    @property
    def unit_peer_data(self) -> Dict:
        """Unit peer relation data object."""
        return self._peers.data[self.unit]

    @property
    def app_peer_data(self) -> Dict:
        """App peer relation data object."""
        return self._peers.data[self.app]

    @property
    def config_server_db(self) -> str:
        """Fetch current the config server database that this unit is connected to."""

        env_var = Path(ENV_VAR_PATH)
        if not env_var.is_file():
            logger.info("no environment variable file")
            return ""

        with open(ENV_VAR_PATH, "r") as file:
            env_vars = file.read()

        for env_var in env_vars.split("\n"):
            if MONGOS_VAR not in env_var:
                continue
            if CONFIG_ARG not in env_var:
                return ""

            # parse config db variable
            return env_var.split(CONFIG_ARG)[1].strip().split(" ")[0]

        return ""

    # END: properties


if __name__ == "__main__":
    ops.main(MongosOperatorCharm)
