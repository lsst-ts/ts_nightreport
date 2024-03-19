# type: ignore
# flake8: noqa
"""initial version

Revision ID: 99e08c61cf29
Revises: 
Create Date: 2024-02-22 15:33:28.118372

"""
import logging

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "99e08c61cf29"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(log: logging.Logger, table_names: set[str]) -> None:
    pass


def downgrade(log: logging.Logger, table_names: set[str]) -> None:
    pass
