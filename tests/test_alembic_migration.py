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

import collections.abc
import contextlib
import os
import subprocess
import uuid

import psycopg
import pytest
import sqlalchemy as sa
import sqlalchemy.engine
import sqlalchemy.types as saty
from lsst.ts.nightreport.testutils import (
    db_config_from_dsn,
    dsn_from_connection_info,
    modify_environ,
)
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncConnection, AsyncEngine
from sqlalchemy.future.engine import Connection

# Length of the site_id field.
SITE_ID_LEN = 16

# Length of urls fields
URLS_LEN = 50


@contextlib.asynccontextmanager
async def create_database(
    postgresql: psycopg.Connection,
) -> collections.abc.AsyncGenerator[AsyncEngine, None]:
    """Create an empty database and set env vars to point to it.

    Parameters
    ----------
    postgresql : `psycopg.Connection`
        Connection to the PostgreSQL server.

    Yields
    ------
    url : `sqlalchemy.ext.asyncio.engine.AsyncEngine`
        URL to database
    """
    with postgresql as conn:
        postgresql_url = f"postgresql://{conn.info.user}@{conn.info.host}:{conn.info.port}/{conn.info.dbname}"
        async_url = sqlalchemy.engine.make_url(postgresql_url)
        async_url = async_url.set(drivername="postgresql+asyncpg")

        dsn = dsn_from_connection_info(conn.info)
        db_config = db_config_from_dsn(dsn)
        with modify_environ(**db_config):
            engine = create_async_engine(async_url)
            yield engine


async def get_column_info(
    connection: AsyncConnection, table: str
) -> list[sa.engine.interfaces.ReflectedColumn]:
    """Get column info for a specified table.

    Parameters
    ----------
    connection : `sqlalchemy.ext.asyncio.engine.AsyncConnection`
        Async connection
    table : `str`
        Table name

    Returns
    -------
    info : `list[dict[str, typing.Any]]`
        A list of dicts, with one entry per column.
        Each dict includes the following keys:
        "name", "type", "nullable", "default", and "autoincrement"
    """

    def _impl(connection: Connection) -> list[sa.engine.interfaces.ReflectedColumn]:
        """Synchronous implementation.

        Inspect does not work with an async connection
        """
        inspector = inspect(connection)
        return inspector.get_columns(table)

    return await connection.run_sync(_impl)


async def get_column_names(connection: AsyncConnection, table: str) -> list[str]:
    """A simplified version of get_column_info that just returns column names.

    Parameters
    ----------
    connection : `sqlalchemy.ext.asyncio.engine.AsyncConnection`
        Async connection
    table : `str`
        Table name

    Returns
    -------
    column_names : `list[str]`
        A list of column names.
    """
    column_info = await get_column_info(connection=connection, table=table)
    return [item["name"] for item in column_info]


async def get_table_names(connection: AsyncConnection) -> list[str]:
    """Get the names of tables in the nightreport database.

    Parameters
    ----------
    connection : `sqlalchemy.ext.asyncio.engine.AsyncConnection`
        Async connection

    Returns
    -------
    table_names : `list[str]`
        A list of table names.
    """

    def _impl(connection: Connection) -> list[str]:
        """Synchronous implementation.

        Inspect does not work with an async connection
        """
        inspector = inspect(connection)
        return inspector.get_table_names()

    return await connection.run_sync(_impl)


def create_old_report_table() -> sa.Table:
    """Make a model of the oldest message table supported by alembic.

    Returns
    -------
    table : `sqlalchemy.Table`
        The table model.
    """
    table = sa.Table(
        "nightreport",
        sa.MetaData(),
        # See https://stackoverflow.com/a/49398042 for UUID:
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", saty.String(length=SITE_ID_LEN)),
        sa.Column(
            "telescope",
            saty.Enum("AuxTel", "Simonyi", name="telescope_enum"),
            nullable=False,
        ),
        sa.Column("summary", saty.Text(), nullable=False),
        sa.Column("telescope_status", saty.Text(), nullable=False),
        sa.Column("confluence_url", saty.String(length=URLS_LEN)),
        sa.Column("day_obs", saty.Integer(), nullable=False),
        sa.Column("user_id", saty.String(), nullable=False),
        sa.Column("user_agent", saty.String(), nullable=False),
        sa.Column(
            "is_valid",
            saty.Boolean(),
            sa.Computed("date_invalidated is null"),
            nullable=False,
        ),
        sa.Column("date_added", saty.DateTime(), nullable=False),
        sa.Column("date_sent", saty.DateTime(), nullable=True),
        sa.Column("date_invalidated", saty.DateTime(), nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["message.id"]),
    )

    for name in (
        "user_id",
        "date_added",
        "date_sent",
    ):
        sa.Index(f"idx_{name}", table.columns[name])

    return table


@pytest.mark.asyncio
async def test_no_report_table(postgresql: psycopg.Connection) -> None:
    async with create_database(postgresql) as engine:
        async with engine.connect() as connection:
            table_names = await get_table_names(connection)
            assert table_names == []

        subprocess.run(["alembic", "upgrade", "head"], env=os.environ.copy())

        async with engine.connect() as connection:
            table_names = await get_table_names(connection)
            assert set(table_names) == {"alembic_version"}
