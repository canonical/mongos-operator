#!/usr/bin/env python3
"""Charm code for `mongos` daemon."""

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
from ops.main import main

from single_kernel_mongo.abstract_charm import AbstractMongoCharm
from single_kernel_mongo.config.literals import Substrates
from single_kernel_mongo.config.relations import PeerRelationNames
from single_kernel_mongo.core.structured_config import MongosCharmConfig
from single_kernel_mongo.managers.mongos_operator import MongosOperator


class MongosVMCharm(AbstractMongoCharm[MongosCharmConfig, MongosOperator]):
    config_type = MongosCharmConfig
    operator_type = MongosOperator
    substrate = Substrates.VM
    peer_rel_name = PeerRelationNames.ROUTER_PEERS
    name = "mongos-test"


if __name__ == "__main__":
    main(MongosVMCharm)
