"""Configuration for MongoDB Charm."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.


from typing import Literal


class Config:
    """Configuration for MongoDB Charm."""

    MONGOS_PORT = 27018
    MONGOS_SOCKET = "/var/snap/charmed-mongodb/common/var/mongodb-27018.sock"
    MONGODB_PORT = 27017
    SUBSTRATE = "vm"
    ENV_VAR_PATH = "/etc/environment"
    MONGODB_SNAP_DATA_DIR = "/var/snap/charmed-mongodb/current"
    MONGOD_CONF_DIR = f"{MONGODB_SNAP_DATA_DIR}/etc/mongod"
    MONGOD_CONF_FILE_PATH = f"{MONGOD_CONF_DIR}/mongod.conf"
    SNAP_PACKAGES = [("charmed-mongodb", "6/edge", 87)]

    class Relations:
        """Relations related config for MongoDB Charm."""

        APP_SCOPE = "app"
        UNIT_SCOPE = "unit"
        PEERS = "router-peers"
        CLUSTER_RELATIONS_NAME = "cluster"
        Scopes = Literal[APP_SCOPE, UNIT_SCOPE]

    class TLS:
        """TLS related config for MongoDB Charm."""

        EXT_PEM_FILE = "external-cert.pem"
        EXT_CA_FILE = "external-ca.crt"
        INT_PEM_FILE = "internal-cert.pem"
        INT_CA_FILE = "internal-ca.crt"
        KEY_FILE_NAME = "keyFile"
        TLS_PEER_RELATION = "certificates"

        SECRET_CA_LABEL = "ca-secret"
        SECRET_KEY_LABEL = "key-secret"
        SECRET_CERT_LABEL = "cert-secret"
        SECRET_CSR_LABEL = "csr-secret"
        SECRET_CHAIN_LABEL = "chain-secret"

    class Secrets:
        """Secrets related constants."""

        SECRET_LABEL = "secret"
        SECRET_CACHE_LABEL = "cache"
        SECRET_KEYFILE_NAME = "keyfile"
        SECRET_INTERNAL_LABEL = "internal-secret"
        SECRET_DELETED_LABEL = "None"
        MAX_PASSWORD_LENGTH = 4096
