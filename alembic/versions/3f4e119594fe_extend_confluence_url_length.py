# type: ignore
# flake8: noqa
"""extend confluence_url length

Revision ID: 3f4e119594fe
Revises: e6dc052f0caf
Create Date: 2024-04-02 11:01:50.116786

"""

import logging

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "3f4e119594fe"
down_revision = "e6dc052f0caf"
branch_labels = None
depends_on = None


NIGHTREPORT_TABLE_NAME = "nightreport"
OLD_URLS_LEN = 50
NEW_URLS_LEN = 200


def upgrade(log: logging.Logger, table_names: set[str]) -> None:
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "confluence_url",
        existing_type=sa.String(length=OLD_URLS_LEN),
        type_=sa.String(length=NEW_URLS_LEN),
        existing_nullable=True,
        nullable=False,
    )


def downgrade(log: logging.Logger, table_names: set[str]) -> None:
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "confluence_url",
        existing_type=sa.String(length=NEW_URLS_LEN),
        type_=sa.String(length=OLD_URLS_LEN),
        existing_nullable=False,
        nullable=True,
    )
