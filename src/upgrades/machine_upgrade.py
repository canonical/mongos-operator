# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""In-place upgrades on machines.

Derived from specification: DA058 - In-Place Upgrades - Kubernetes v2
(https://docs.google.com/document/d/1tLjknwHudjcHs42nzPVBNkHs98XxAOT2BXGGpP7NyEU/)
"""
import json
import logging
import typing

import ops

from config import Config
from charms.mongos.v0.upgrade_helpers import AbstractUpgrade, UnitState

logger = logging.getLogger(__name__)

_SNAP_REVISION = str(Config.SNAP_PACKAGES[0][2])


class Upgrade(AbstractUpgrade):
    """In-place upgrades on machines."""

    @property
    def unit_state(self) -> typing.Optional[UnitState]:
        """Returns the unit state."""
        if (
            self._unit_workload_container_version is not None
            and self._unit_workload_container_version
            != self._app_workload_container_version
        ):
            logger.debug("Unit refresh state: outdated")
            return UnitState.OUTDATED
        return super().unit_state

    @unit_state.setter
    def unit_state(self, value: UnitState) -> None:
        # Super call
        AbstractUpgrade.unit_state.fset(self, value)

    def _get_unit_healthy_status(self) -> ops.StatusBase:
        if (
            self._unit_workload_container_version
            == self._app_workload_container_version
        ):
            return ops.ActiveStatus(
                f'MongoDB {self._unit_workload_version} running; Snap revision {self._unit_workload_container_version}; Charm revision {self._current_versions["charm"]}'
            )
        return ops.ActiveStatus(
            f'MongoDB {self._unit_workload_version} running; Snap revision {self._unit_workload_container_version} (outdated); Charm revision {self._current_versions["charm"]}'
        )

    @property
    def app_status(self) -> typing.Optional[ops.StatusBase]:
        """App upgrade status."""
        if not self.is_compatible:
            logger.info(
                "Refresh incompatible. If you accept potential *data loss* and *downtime*, you can continue by running `force-refresh-start` action on each remaining unit"
            )
            return ops.BlockedStatus(
                "Refresh incompatible. Rollback to previous revision with `juju refresh`"
            )
        return super().app_status

    @property
    def _unit_workload_container_versions(self) -> typing.Dict[str, str]:
        """{Unit name: installed snap revision}."""
        versions = {}
        for unit in self._sorted_units:
            if version := (self._peer_relation.data[unit].get("snap_revision")):
                versions[unit.name] = version
        return versions

    @property
    def _unit_workload_container_version(self) -> typing.Optional[str]:
        """Installed snap revision for this unit."""
        return self._unit_databag.get("snap_revision")

    @_unit_workload_container_version.setter
    def _unit_workload_container_version(self, value: str):
        self._unit_databag["snap_revision"] = value

    @property
    def _app_workload_container_version(self) -> str:
        """Snap revision for current charm code."""
        return _SNAP_REVISION

    @property
    def _unit_workload_version(self) -> typing.Optional[str]:
        """Installed OpenSearch version for this unit."""
        return self._unit_databag.get("workload_version")

    @_unit_workload_version.setter
    def _unit_workload_version(self, value: str):
        self._unit_databag["workload_version"] = value

    @property
    def authorized(self) -> bool:
        """Whether this unit is authorized to upgrade.

        Only applies to machine charm.

        Raises:
            PrecheckFailed: App is not ready to upgrade
        """
        assert (
            self._unit_workload_container_version
            != self._app_workload_container_version
        )
        assert self.versions_set
        for index, unit in enumerate(self._sorted_units):
            if unit.name == self._unit.name:
                # Higher number units have already upgraded
                if index == 0:
                    if (
                        json.loads(self._app_databag["versions"])["charm"]
                        == self._current_versions["charm"]
                    ):
                        # Assumes charm version uniquely identifies charm revision
                        logger.debug("Rollback detected. Skipping pre-refresh check")
                    else:
                        # Run pre-upgrade check
                        # (in case user forgot to run pre-upgrade-check action)
                        self.pre_upgrade_check()
                        logger.debug(
                            "Pre-refresh check after `juju refresh` successful"
                        )

                return True
            state = self._peer_relation.data[unit].get("state")
            if state:
                state = UnitState(state)
            if (
                self._unit_workload_container_versions.get(unit.name)
                != self._app_workload_container_version
                or state is not UnitState.HEALTHY
            ):
                # Waiting for higher number units to upgrade
                return False
        return False

    def upgrade_unit(self, *, charm) -> None:
        """Runs the upgrade procedure.

        Only applies to machine charm.
        """
        logger.debug(f"Upgrading {self.authorized=}")
        self.unit_state = UnitState.UPGRADING
        charm.stop_mongos_service()
        charm.install_snap_packages(packages=Config.SNAP_PACKAGES)
        charm.start_mongos_service()
        self._unit_databag["snap_revision"] = _SNAP_REVISION
        self._unit_workload_version = self._current_versions["workload"]
        logger.debug(f"Saved {_SNAP_REVISION} in unit databag after refresh")

        # post upgrade check should be retried in case of failure, for this it is necessary to
        # emit a separate event.
        charm.upgrade.post_upgrade_event.emit()

    def save_snap_revision_after_first_install(self):
        """Set snap revision on first install."""
        self._unit_workload_container_version = _SNAP_REVISION
        self._unit_workload_version = self._current_versions["workload"]
        logger.debug(
            f'Saved {_SNAP_REVISION=} and {self._current_versions["workload"]=} in unit databag after first install'
        )
