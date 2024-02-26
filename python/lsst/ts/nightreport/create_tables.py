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
URLS_LEN = 50


def create_nightreport_table(metadata: sa.MetaData) -> sa.Table:
    """Make a model of the night report table.

    Parameters
    ----------
    metadata: sa.MetaData
        SQLAlchemy metadata object.

    Returns
    -------
    table: sa.Table
        SQLAlchemy table object for night report.
    """
    table = sa.Table(
        "nightreport",
        metadata,
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
