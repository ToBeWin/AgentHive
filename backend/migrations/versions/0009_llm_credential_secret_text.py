"""widen llm credential secret storage

Revision ID: 0009_llm_credential_secret_text
Revises: 0008_knowledge_chunk_embeddings
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_llm_credential_secret_text"
down_revision = "0008_knowledge_chunk_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "llm_credentials",
        "secret_ref",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "llm_credentials",
        "secret_ref",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
