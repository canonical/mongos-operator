"""Machine Charm specific functions for operating MongoDB."""
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from config import Config

logger = logging.getLogger(__name__)

DB_PROCESS = "/usr/bin/mongod"
ROOT_USER_GID = 0
MONGO_USER = "snap_daemon"


def add_args_to_env(var: str, args: str):
    """Adds the provided arguments to the environment as the provided variable."""
    with open(Config.ENV_VAR_PATH, "r") as env_var_file:
        env_vars = env_var_file.readlines()

    args_added = False
    for index, line in enumerate(env_vars):
        if var in line:
            args_added = True
            env_vars[index] = f"{var}={args}"

    # if it is the first time adding these args to the file - will will need to append them to the
    # file
    if not args_added:
        env_vars.append(f"{var}={args}")

    with open(Config.ENV_VAR_PATH, "w") as service_file:
        service_file.writelines(env_vars)
