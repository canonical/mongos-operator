# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for handling Mongos in-place upgrades."""

import logging
from typing import Optional
from ops import BlockedStatus
from ops.charm import ActionEvent, CharmBase
from ops.framework import EventBase, EventSource
from ops.model import ActiveStatus
from overrides import override
from charms.mongos.v0.upgrade_helpers import (
    ROLLBACK_INSTRUCTIONS,
    GenericMongosUpgrade,
    PEER_RELATION_ENDPOINT_NAME,
    PeerRelationNotReady,
    UnitState,
    PrecheckFailed,
)

from config import Config
from upgrades import machine_upgrade

logger = logging.getLogger(__name__)


# BEGIN: Exceptions


class ClusterNotHealthyError(Exception):
    """Raised when the cluster is not healthy."""


# END: Exceptions


class _PostUpgradeCheckMongos(EventBase):
    """Run post upgrade check on Mongos to verify that the cluster is healhty."""

    def __init__(self, handle):
        super().__init__(handle)


class MongosUpgrade(GenericMongosUpgrade):
    """Handlers for upgrade events."""

    post_upgrade_event = EventSource(_PostUpgradeCheckMongos)

    def __init__(self, charm: CharmBase):
        self.charm = charm
        super().__init__(charm, PEER_RELATION_ENDPOINT_NAME)

    @override
    def _observe_events(self, charm: CharmBase) -> None:
        self.framework.observe(
            charm.on[PEER_RELATION_ENDPOINT_NAME].relation_created,
            self._on_upgrade_peer_relation_created,
        )
        self.framework.observe(
            charm.on[PEER_RELATION_ENDPOINT_NAME].relation_changed,
            self._reconcile_upgrade,
        )
        self.framework.observe(charm.on.upgrade_charm, self._on_upgrade_charm)

        self.framework.observe(
            charm.on["force-upgrade"].action, self._on_force_upgrade_action
        )
        self.framework.observe(self.post_upgrade_event, self.run_post_upgrade_check)

    # BEGIN: properties
    @property
    @override
    def _upgrade(self) -> Optional[machine_upgrade.Upgrade]:
        try:
            return machine_upgrade.Upgrade(self.charm)
        except PeerRelationNotReady:
            return None

    # END: properties

    # BEGIN: Event handlers
    def _on_upgrade_peer_relation_created(self, _) -> None:
        self._upgrade.save_snap_revision_after_first_install()
        if self.charm.unit.is_leader():
            if not self._upgrade.in_progress:
                # Save versions on initial start
                self._upgrade.set_versions_in_app_databag()

    def _reconcile_upgrade(self, _=None):
        """Handle upgrade events."""
        if not self._upgrade:
            logger.debug("Peer relation not available")
            return
        if not self._upgrade.versions_set:
            logger.debug("Peer relation not ready")
            return
        if self.charm.unit.is_leader() and not self._upgrade.in_progress:
            # Run before checking `self._upgrade.is_compatible` in case incompatible upgrade was
            # forced & completed on all units.
            self._upgrade.set_versions_in_app_databag()
        if not self._upgrade.is_compatible:
            self._set_upgrade_status()
            return
        if self._upgrade.unit_state is UnitState.OUTDATED:
            try:
                authorized = self._upgrade.authorized
            except PrecheckFailed as exception:
                self._set_upgrade_status()
                self.charm.status.set_and_share_status(exception.status)
                logger.debug(f"Set unit status to {self.charm.unit.status}")
                logger.error(exception.status.message)
                return
            if authorized:
                self._set_upgrade_status()
                self._upgrade.upgrade_unit(charm=self.charm)
            else:
                self._set_upgrade_status()
                logger.debug("Waiting to upgrade")
                return
        self._set_upgrade_status()

    def _on_upgrade_charm(self, _):
        if self.charm.unit.is_leader():
            if not self._upgrade.in_progress:
                logger.info("Charm upgraded. MongoDB snap version unchanged")

        self._reconcile_upgrade()

    def _on_force_upgrade_action(self, event: ActionEvent) -> None:
        if not self._upgrade or not self._upgrade.in_progress:
            message = "No upgrade in progress"
            logger.debug(f"Force upgrade event failed: {message}")
            event.fail(message)
            return
        if self._upgrade.unit_state != "outdated":
            message = "Unit already upgraded"
            logger.debug(f"Force upgrade event failed: {message}")
            event.fail(message)
            return
        logger.debug("Forcing upgrade")
        event.log(f"Forcefully upgrading {self.charm.unit.name}")
        self._upgrade.upgrade_unit(charm=self.charm)
        event.set_results({"result": f"Forcefully upgraded {self.charm.unit.name}"})
        logger.debug("Forced upgrade")

    def run_post_upgrade_check(self, event) -> None:
        """Runs post-upgrade checks for after mongos router upgrade."""
        # The mongos service cannot be considered ready until it has a config-server. Therefore
        # it is not necessary to do any sophisticated checks.
        if not self.charm.mongos_initialised:
            self._upgrade.unit_state = UnitState.HEALTHY
            return

        self.run_post_upgrade_checks(event)

    # END: Event handlers

    # BEGIN: Helpers
    def _set_upgrade_status(self):
        # In the future if we decide to support app statuses, we will need to handle this
        # differently. Specifically ensuring that upgrade status for apps status has the lowest
        # priority
        if self.charm.unit.is_leader():
            self.charm.app.status = self._upgrade.app_status or ActiveStatus()

        # Set/clear upgrade unit status if no other unit status - upgrade status for units should
        # have the lowest priority.
        if isinstance(self.charm.unit.status, ActiveStatus) or (
            isinstance(self.charm.unit.status, BlockedStatus)
            and self.charm.unit.status.message.startswith(
                "Rollback with `juju refresh`. Pre-upgrade check failed:"
            )
        ):
            self.charm.status.set_and_share_status(
                self._upgrade.get_unit_juju_status() or ActiveStatus()
            )

    def run_post_upgrade_checks(self, event) -> None:
        """Runs post-upgrade checks for after a shard/config-server/replset/cluster upgrade."""
        logger.debug("-----\nchecking mongos running\n----")
        if not self.charm.cluster.is_mongos_running():
            logger.debug(
                "Waiting for mongos router to be ready before finalising upgrade."
            )
            event.defer()
            return

        logger.debug("-----\nchecking is_mongos_able_to_read_write\n----")
        if not self.is_mongos_able_to_read_write():
            logger.error("mongos is not able to read/write after upgrade.")
            logger.info(ROLLBACK_INSTRUCTIONS)
            self.charm.status.set_and_share_status(Config.Status.UNHEALTHY_UPGRADE)
            event.defer()
            return

        if self.charm.unit.status == Config.Status.UNHEALTHY_UPGRADE:
            self.charm.status.set_and_share_status(ActiveStatus())

        logger.debug("upgrade of unit succeeded.")
        self._upgrade.unit_state = UnitState.HEALTHY

    # END: helpers
