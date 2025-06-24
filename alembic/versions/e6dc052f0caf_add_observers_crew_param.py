# type: ignore
# flake8: noqa
"""add observers_crew param

Revision ID: e6dc052f0caf
Revises: 99e08c61cf29
Create Date: 2024-03-06 13:56:08.634211

"""

import logging

import sqlalchemy as sa
import sqlalchemy.types as saty

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "e6dc052f0caf"
down_revision = "99e08c61cf29"
branch_labels = None
depends_on = None

NIGHTREPORT_TABLE_NAME = "nightreport"


def upgrade(log: logging.Logger, table_names: set[str]) -> None:
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    log.info("Add column 'observers_crew'")
    op.add_column(
        NIGHTREPORT_TABLE_NAME,
        sa.Column("observers_crew", saty.ARRAY(sa.Text), nullable=True),
    )

    # "{ }" is Postgres syntax for an empty list
    op.execute(f"UPDATE {NIGHTREPORT_TABLE_NAME} SET observers_crew = '{{ }}'")
    op.alter_column(NIGHTREPORT_TABLE_NAME, "observers_crew", nullable=False)


def downgrade(log: logging.Logger, table_names: set[str]):
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    log.info("Drop columns 'observers_crew'")
    op.drop_column(NIGHTREPORT_TABLE_NAME, "observers_crew")
