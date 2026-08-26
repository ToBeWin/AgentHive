"""add previous_secret_ref to channel_configs for secret rotation

Revision ID: 0015_channel_previous_secret_ref
Revises: 0014_media_generation_job_runtime_indexes
Create Date: 2026-06-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_channel_previous_secret_ref"
down_revision = "0014_media_generation_job_runtime_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_configs",
        sa.Column("previous_secret_ref", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_configs", "previous_secret_ref")
