"""add media generation jobs

Revision ID: 0013_media_generation_jobs
Revises: 0012_license_kb_capacity
Create Date: 2026-06-16 00:00:00.000000
"""

from alembic import op


revision = "0013_media_generation_jobs"
down_revision = "0012_license_kb_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE media_generation_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            user_id UUID REFERENCES users(id),
            department_id UUID REFERENCES departments(id),
            agent_id UUID REFERENCES agent_instances(id),
            conversation_id UUID REFERENCES conversation_sessions(id),
            request_id VARCHAR(64),
            kind VARCHAR(20) NOT NULL,
            mode VARCHAR(40) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'queued',
            provider_key VARCHAR(80) NOT NULL,
            provider_type VARCHAR(80) NOT NULL,
            model_key VARCHAR(120) NOT NULL,
            routing_key VARCHAR(120) NOT NULL,
            prompt TEXT NOT NULL,
            negative_prompt TEXT,
            reference_assets JSONB NOT NULL DEFAULT '[]',
            request_parameters JSONB NOT NULL DEFAULT '{}',
            normalized_parameters JSONB NOT NULL DEFAULT '{}',
            output_storage JSONB NOT NULL DEFAULT '{}',
            outputs JSONB NOT NULL DEFAULT '[]',
            external_job_id VARCHAR(160),
            error_message TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX ix_media_generation_jobs_tenant_created ON media_generation_jobs (tenant_id, created_at)")
    op.execute("CREATE INDEX ix_media_generation_jobs_tenant_status ON media_generation_jobs (tenant_id, status, created_at)")
    op.execute("CREATE INDEX ix_media_generation_jobs_tenant_kind ON media_generation_jobs (tenant_id, kind, created_at)")
    op.execute("CREATE INDEX ix_media_generation_jobs_agent ON media_generation_jobs (tenant_id, agent_id, created_at)")
    op.execute("CREATE INDEX ix_media_generation_jobs_request ON media_generation_jobs (tenant_id, request_id)")
    op.execute("CREATE INDEX ix_media_generation_jobs_external ON media_generation_jobs (tenant_id, external_job_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS media_generation_jobs CASCADE")
