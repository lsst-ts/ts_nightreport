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

__all__ = ["NightReportDatabase"]

import asyncio

import sqlalchemy as sa
import sqlalchemy.engine
import structlog
from sqlalchemy.ext.asyncio import create_async_engine


class NightReportDatabase:
    """Connection to the night report database and tables creation.

    Create report table if it doesn't exist.

    Parameters
    ----------
    nightreport_table : `sa.Table`
        Report table.
    url : `str`
        URL of night report database server in the form:
        postgresql://[user[:password]@][netloc][:port][/dbname]
    """

    def __init__(self, nightreport_table: sa.Table, url: str):
        self._closed = False
        self.url = url
        self.logger = structlog.get_logger("NightReportDatabase")
        sa_url = sqlalchemy.engine.make_url(url)
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
        self.engine = create_async_engine(sa_url, future=True)
        self.nightreport_table = nightreport_table
        self.start_task = asyncio.create_task(self.start())

    async def start(self) -> None:
        """Create the table in the database."""
        self.logger.info("Create table")
        async with self.engine.begin() as connection:
            await connection.run_sync(self.nightreport_table.metadata.create_all)

    async def close(self) -> None:
        """Close the database engine and all connections."""
        if self._closed:
            return
        self._closed = True
        self.start_task.cancel()
        await self.engine.dispose()
