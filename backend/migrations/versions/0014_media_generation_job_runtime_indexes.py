"""add media generation runtime indexes

Revision ID: 0014_media_generation_job_runtime_indexes
Revises: 0013_media_generation_jobs
Create Date: 2026-06-16 00:00:00.000000
"""

from alembic import op


revision = "0014_media_generation_job_runtime_indexes"
down_revision = "0013_media_generation_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_generation_jobs_tenant_user_created
        ON media_generation_jobs (tenant_id, user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_generation_jobs_tenant_department_created
        ON media_generation_jobs (tenant_id, department_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_generation_jobs_running_user_updated
        ON media_generation_jobs (tenant_id, user_id, updated_at ASC)
        WHERE status = 'running' AND external_job_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_generation_jobs_running_department_updated
        ON media_generation_jobs (tenant_id, department_id, updated_at ASC)
        WHERE status = 'running' AND external_job_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_media_generation_jobs_provider_external
        ON media_generation_jobs (provider_key, external_job_id)
        WHERE external_job_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_media_generation_jobs_provider_external")
    op.execute("DROP INDEX IF EXISTS ix_media_generation_jobs_running_department_updated")
    op.execute("DROP INDEX IF EXISTS ix_media_generation_jobs_running_user_updated")
    op.execute("DROP INDEX IF EXISTS ix_media_generation_jobs_tenant_department_created")
    op.execute("DROP INDEX IF EXISTS ix_media_generation_jobs_tenant_user_created")
