"""Configuration for MongoDB Charm."""

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Literal
from urllib.parse import quote
from ops.model import BlockedStatus


class Config:
    """Configuration for MongoDB Charm."""

    MONGOS_PORT = 27018
    MONGOS_SOCKET = "/var/snap/charmed-mongodb/common/var/mongodb-27018.sock"
    MONGOS_SOCKET_URI_FMT = quote(MONGOS_SOCKET, safe="")
    MONGODB_PORT = 27017
    SUBSTRATE = "vm"
    ENV_VAR_PATH = "/etc/environment"
    MONGODB_SNAP_DATA_DIR = "/var/snap/charmed-mongodb/current"
    MONGOD_CONF_DIR = f"{MONGODB_SNAP_DATA_DIR}/etc/mongod"
    MONGOD_CONF_FILE_PATH = f"{MONGOD_CONF_DIR}/mongod.conf"
    SNAP_PACKAGES = [("charmed-mongodb", "6/edge", 122)]

    class Relations:
        """Relations related config for MongoDB Charm."""

        APP_SCOPE = "app"
        UNIT_SCOPE = "unit"
        PEERS = "router-peers"
        CLUSTER_RELATIONS_NAME = "cluster"
        Scopes = Literal[APP_SCOPE, UNIT_SCOPE]

    class TLS:
        """TLS related config for MongoDB Charm."""

        KEY_FILE_NAME = "keyFile"
        TLS_PEER_RELATION = "certificates"
        SECRET_KEY_LABEL = "key-secret"

        EXT_PEM_FILE = "external-cert.pem"
        EXT_CA_FILE = "external-ca.crt"
        INT_PEM_FILE = "internal-cert.pem"
        INT_CA_FILE = "internal-ca.crt"
        SECRET_CA_LABEL = "ca-secret"
        SECRET_CERT_LABEL = "cert-secret"
        SECRET_CSR_LABEL = "csr-secret"
        SECRET_CHAIN_LABEL = "chain-secret"

    class Secrets:
        """Secrets related constants."""

        SECRET_LABEL = "secret"
        SECRET_CACHE_LABEL = "cache"
        SECRET_KEYFILE_NAME = "keyfile"
        SECRET_INTERNAL_LABEL = "internal-secret"
        USERNAME = "username"
        PASSWORD = "password"
        SECRET_DELETED_LABEL = "None"
        MAX_PASSWORD_LENGTH = 4096

    class Status:
        """Status related constants.

        TODO: move all status messages here.
        """

        STATUS_READY_FOR_UPGRADE = "status-shows-ready-for-upgrade"

        # TODO Future PR add more status messages here as constants
        UNHEALTHY_UPGRADE = BlockedStatus("Unhealthy after upgrade.")

    class Substrate:
        """Substrate related constants."""

        VM = "vm"
        K8S = "k8s"

    class Role:
        """Role config names for MongoDB Charm."""

        CONFIG_SERVER = "config-server"
        REPLICATION = "replication"
        SHARD = "shard"
        MONGOS = "mongos"
