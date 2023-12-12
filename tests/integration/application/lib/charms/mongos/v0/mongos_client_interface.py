# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""In this class, we manage relations between config-servers and shards.

This class handles the sharing of secrets between sharded components, adding shards, and removing
shards.
"""
import logging
from ops.framework import Object
from ops.charm import CharmBase
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseProvides,
    DatabaseRequires,
)


logger = logging.getLogger(__name__)
DATABASE_KEY = "database"
USER_ROLES_KEY = "extra-user-roles"
MONGOS_RELATION_NAME = "mongos_proxy"

# The unique Charmhub library identifier, never change it
LIBID = "58ad1ccca4974932ba22b97781b9b2a0"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 1


class MongosProvider(Object):
    """Manage relations between the mongos router and the application on the mongos side."""

    def __init__(self, charm: CharmBase, relation_name: str = MONGOS_RELATION_NAME) -> None:
        """Constructor for MongosProvider object."""
        self.relation_name = relation_name
        self.charm = charm
        self.database_provides = DatabaseProvides(self.charm, relation_name=self.relation_name)

        super().__init__(charm, self.relation_name)
        self.framework.observe(
            charm.on[self.relation_name].relation_changed, self._on_relation_changed
        )

        # TODO Future PRs handle relation broken

    def _on_relation_changed(self, event) -> None:
        """Handles updating the database and extra user roles."""
        if not self.charm.unit.is_leader():
            return

        relation_data = event.relation.data[event.app]
        new_database_name = relation_data.get(DATABASE_KEY, self.charm.database)
        new_extra_user_roles = relation_data.get(USER_ROLES_KEY, self.charm.extra_user_roles)

        if new_database_name != self.charm.database:
            self.charm.set_database(new_database_name)

        if new_extra_user_roles != self.charm.extra_user_roles:
            if isinstance(new_extra_user_roles, str):
                new_extra_user_roles = [new_extra_user_roles]

            self.charm.set_user_role(new_extra_user_roles)

    def update_connection_info(self, config) -> None:
        """Sends the URI to the related parent application"""
        for relation in self.model.relations[MONGOS_RELATION_NAME]:
            self.database_provides.set_credentials(relation.id, config.username, config.password)
            self.database_provides.set_database(relation.id, config.database)
            self.database_provides.set_uris(
                relation.id,
                config.uri,
            )


# TODO informative docstring on how to use this INCLUDE SOMETHING ON HOW extra_user_roles should be formatted
class MongosRequirer(Object):
    """Manage relations between the mongos router and the application on the application side."""

    def __init__(
        self,
        charm: CharmBase,
        database_name: str,
        extra_user_roles: str,
        relation_name: str = MONGOS_RELATION_NAME,
    ) -> None:
        """Constructor for MongosRequirer object."""
        self.relation_name = relation_name
        self.charm = charm

        if not database_name:
            database_name = f"{self.charm.app}-mongos"

        self.database_requires = DatabaseRequires(
            self.charm,
            relation_name=self.relation_name,
            database_name=database_name,
            extra_user_roles=extra_user_roles,
        )

        super().__init__(charm, self.relation_name)
        # TODO Future PRs handle relation broken
