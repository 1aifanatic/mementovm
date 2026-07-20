"""add approval expiry

Revision ID: 20260720_0002
Revises: 20260720_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_0002"
down_revision = "20260720_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("approvals")}
    if "expires_at" not in columns:
        op.add_column(
            "approvals", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        if bind.dialect.name == "postgresql":
            op.execute("UPDATE approvals SET expires_at = requested_at + INTERVAL '30 minutes'")
        else:
            op.execute("UPDATE approvals SET expires_at = requested_at")
        with op.batch_alter_table("approvals") as batch:
            batch.alter_column("expires_at", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("approvals")}
    if "expires_at" in columns:
        with op.batch_alter_table("approvals") as batch:
            batch.drop_column("expires_at")
