# This file is part of ts_nightreport.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

__all__ = [
    "create_shared_state",
    "delete_shared_state",
    "get_shared_state",
    "create_db_url",
    "get_env",
]

import logging
import os
import urllib

import sqlalchemy as sa

from .create_tables import SITE_ID_LEN, create_nightreport_table
from .database import NightReportDatabase

_shared_state: None | SharedState = None


def get_env(name: str, default: None | str = None) -> str:
    """Get a value from an environment variable.

    Parameters
    ----------
    name
        The name of the environment variable.
    default
        The default value; if None then raise ValueError if absent.
    """
    if default is not None and not isinstance(default, str):
        raise ValueError(f"default={default!r} must be a str or None")
    value = os.environ.get(name, default)
    if value is None:
        raise ValueError(f"You must specify environment variable {name}")
    return value


def create_db_url() -> str:
    """Create the nightreport database URL from environment variables."""
    nightreport_db_user = get_env("NIGHTREPORT_DB_USER", "nightreport")
    nightreport_db_password = get_env("NIGHTREPORT_DB_PASSWORD", "")
    nightreport_db_host = get_env("NIGHTREPORT_DB_HOST", "localhost")
    nightreport_db_port = int(get_env("NIGHTREPORT_DB_PORT", "5432"))
    nightreport_db_database = get_env("NIGHTREPORT_DB_DATABASE", "nightreport")
    encoded_db_password = urllib.parse.quote_plus(nightreport_db_password)
    return (
        f"postgresql+asyncpg://{nightreport_db_user}:{encoded_db_password}"
        f"@{nightreport_db_host}:{nightreport_db_port}"
        f"/{nightreport_db_database}"
    )


class SharedState:
    """Shared application state.

    All attributes are set by environment variables.

    Attributes
    ----------
    nightreport_db : sa.Table
    site_id : str
        Name identifying where the nightreport service is running.
        Values include: "summit" and "base".

    Notes
    -----
    Reads the following env variables:

    nightreport_db_user
        Nightreport database user name.
    nightreport_db_password
        Nightreport database password.
    nightreport_db_host
        Nightreport database TCP/IP host.
    nightreport_db_port
        Nightreport database TCP/IP port.
    nightreport_db_database
        Name of nightreport database.
    site_id
        String identifying where the nightreport service is running.
        Values include: "summit" and "base".
    """

    def __init__(self):  # type: ignore
        self.site_id = get_env("SITE_ID")
        if len(self.site_id) > SITE_ID_LEN:
            raise ValueError(
                f"SITE_ID={self.site_id!r} too long; max length={SITE_ID_LEN}"
            )
        self.log = logging.getLogger("nightreport")
        self.metadata = sa.MetaData()
        self.nightreport_db = NightReportDatabase(
            nightreport_table=create_nightreport_table(self.metadata),
            url=create_db_url(),
        )


async def create_shared_state() -> None:
    """Create, start and then set the application shared state.

    Raises
    ------
    RuntimeError
            If the shared state has already been created.
    """
    global _shared_state
    if _shared_state is not None:
        raise RuntimeError("Shared state already created")
    state = SharedState()
    await state.nightreport_db.start_task
    _shared_state = state


async def delete_shared_state() -> None:
    """Delete and then close the application shared state."""
    global _shared_state
    if _shared_state is None:
        return
    state = _shared_state
    _shared_state = None
    await state.nightreport_db.close()


def get_shared_state() -> SharedState:
    """Get the application shared state.

    Raises
    ------
    RuntimeError
            If the shared state has not been created.
    """
    global _shared_state
    if _shared_state is None:
        raise RuntimeError("Shared state not created")
    return _shared_state


def has_shared_state() -> bool:
    """Has the application shared state been created?"""
    global _shared_state
    return _shared_state is not None
