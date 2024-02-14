"""Configuration definition."""

__all__ = ["NightReportDatabase"]

import asyncio

import sqlalchemy as sa
import sqlalchemy.engine
import structlog
from sqlalchemy.ext.asyncio import create_async_engine


class NightReportDatabase:
    """Connection to the night report database and tables creation.

    Creates report table if it doesn't exist.

    Parameters
    ----------
    nightreport_table: sa.Table
        Report table.
    url: str
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
