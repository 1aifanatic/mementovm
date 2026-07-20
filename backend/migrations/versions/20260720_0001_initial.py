"""Create the MementoVM durable store.

Revision ID: 20260720_0001
Revises: None
"""
from alembic import op

from backend.app.db import Base
from backend.app import models  # noqa: F401


revision = "20260720_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)

