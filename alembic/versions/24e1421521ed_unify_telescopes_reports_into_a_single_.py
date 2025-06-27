"""unify telescopes reports into a single one

Revision ID: 24e1421521ed
Revises: 3f4e119594fe
Create Date: 2025-06-17 11:08:22.398529

"""

import logging

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "24e1421521ed"
down_revision = "3f4e119594fe"
branch_labels = None
depends_on = None


NIGHTREPORT_TABLE_NAME = "nightreport"


def upgrade(log: logging.Logger, table_names: set[str]) -> None:
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    log.info("Add column 'weather'")
    op.add_column(
        NIGHTREPORT_TABLE_NAME,
        sa.Column("weather", sa.Text, nullable=True),
    )

    log.info("Add column 'maintel_summary'")
    op.add_column(
        NIGHTREPORT_TABLE_NAME,
        sa.Column("maintel_summary", sa.Text, nullable=True),
    )

    log.info("Add column 'auxtel_summary'")
    op.add_column(
        NIGHTREPORT_TABLE_NAME,
        sa.Column("auxtel_summary", sa.Text, nullable=True),
    )

    log.info("Make 'telescope' column nullable")
    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "telescope",
        nullable=True,
    )

    log.info("Make 'telescope_status' column nullable")
    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "telescope_status",
        nullable=True,
    )


def downgrade(log: logging.Logger, table_names: set[str]) -> None:
    if NIGHTREPORT_TABLE_NAME not in table_names:
        log.info(f"No {NIGHTREPORT_TABLE_NAME} table; nothing to do")
        return

    log.info("Drop column 'weather'")
    op.drop_column(NIGHTREPORT_TABLE_NAME, "weather")

    log.info("Drop column 'maintel_summary'")
    op.drop_column(NIGHTREPORT_TABLE_NAME, "maintel_summary")

    log.info("Drop column 'auxtel_summary'")
    op.drop_column(NIGHTREPORT_TABLE_NAME, "auxtel_summary")

    log.info("Make 'telescope' column not nullable")
    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "telescope",
        nullable=False,
    )
    log.info("Make 'telescope_status' column not nullable")
    op.alter_column(
        NIGHTREPORT_TABLE_NAME,
        "telescope_status",
        nullable=False,
    )
