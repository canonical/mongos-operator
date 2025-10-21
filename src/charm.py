#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
"""Charm code for `mongos` daemon."""

import logging

from ops.main import main
from ops.log import JujuLogHandler
from single_kernel_mongo.abstract_charm import AbstractMongoCharm
from single_kernel_mongo.config.literals import Substrates
from single_kernel_mongo.config.relations import PeerRelationNames
from single_kernel_mongo.core.structured_config import MongosCharmConfig
from single_kernel_mongo.managers.mongos_operator import MongosOperator

# Show logger name (module name) in logs
root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if isinstance(handler, JujuLogHandler):
        handler.setFormatter(logging.Formatter("{name}:{message}", style="{"))
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class MongosVMCharm(AbstractMongoCharm[MongosCharmConfig, MongosOperator]):
    config_type = MongosCharmConfig
    operator_type = MongosOperator
    substrate = Substrates.VM
    peer_rel_name = PeerRelationNames.ROUTER_PEERS
    name = "mongos"


if __name__ == "__main__":
    main(MongosVMCharm)
