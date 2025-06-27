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

__all__ = [
    "SITE_ID_LEN",
    "URLS_LEN",
    "create_nightreport_table",
]

import uuid

import sqlalchemy as sa
import sqlalchemy.types as saty
from sqlalchemy.dialects.postgresql import UUID

# Length of the site_id field.
SITE_ID_LEN = 16

# Length of urls fields
URLS_LEN = 200


def create_nightreport_table(metadata: sa.MetaData) -> sa.Table:
    """Make a model of the night report table.

    Parameters
    ----------
    metadata : `sa.MetaData`
        SQLAlchemy metadata object.

    Returns
    -------
    table : `sa.Table`
        SQLAlchemy table object for night report.
    """
    table = sa.Table(
        "nightreport",
        metadata,
        # See https://stackoverflow.com/a/49398042 for UUID:
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("site_id", saty.String(length=SITE_ID_LEN)),
        # Deprecated 2025-06-16
        sa.Column(
            "telescope",
            saty.Enum("AuxTel", "Simonyi", name="telescope_enum"),
            nullable=True,
        ),
        sa.Column("summary", saty.Text(), nullable=False),
        # Deprecated 2025-06-16
        sa.Column("telescope_status", saty.Text(), nullable=True),
        # Added 2025-06-16
        sa.Column("weather", saty.Text(), nullable=True),
        # Added 2025-06-16
        sa.Column("maintel_summary", saty.Text(), nullable=True),
        # Added 2025-06-16
        sa.Column("auxtel_summary", saty.Text(), nullable=True),
        sa.Column("confluence_url", saty.String(length=URLS_LEN), nullable=False),
        sa.Column("day_obs", saty.Integer(), nullable=False),
        sa.Column("user_id", saty.String(), nullable=False),
        sa.Column("user_agent", saty.String(), nullable=False),
        sa.Column("date_added", saty.DateTime(), nullable=False),
        sa.Column("date_sent", saty.DateTime(), nullable=True),
        sa.Column(
            "is_valid",
            saty.Boolean(),
            sa.Computed("date_invalidated is null"),
            nullable=False,
        ),
        sa.Column("date_invalidated", saty.DateTime(), nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
        # Added 2024-03-06
        sa.Column("observers_crew", saty.ARRAY(sa.Text), nullable=False),
        # Constraints
        sa.ForeignKeyConstraint(["parent_id"], ["nightreport.id"]),
    )

    for name in (
        "user_id",
        "date_added",
        "date_sent",
    ):
        sa.Index(f"idx_{name}", table.columns[name])

    return table
