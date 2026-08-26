"""initial enterprise core

Revision ID: 0001_initial_enterprise_core
Revises:
Create Date: 2026-06-08
"""

from collections.abc import Sequence

from alembic import op

revision = "0001_initial_enterprise_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE tenants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            slug VARCHAR(50) NOT NULL UNIQUE,
            license_key TEXT,
            license_type VARCHAR(20) NOT NULL DEFAULT 'basic',
            license_expires_at TIMESTAMPTZ,
            max_users INTEGER NOT NULL DEFAULT 50,
            max_agents INTEGER NOT NULL DEFAULT 5,
            max_kb_size_gb NUMERIC(10,2) NOT NULL DEFAULT 5.0,
            config JSONB NOT NULL DEFAULT '{}',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE departments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            parent_id UUID REFERENCES departments(id),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE cost_centers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            department_id UUID REFERENCES departments(id),
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            monthly_budget_usd NUMERIC(12,4),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            email VARCHAR(255) NOT NULL,
            username VARCHAR(50),
            hashed_password TEXT NOT NULL,
            full_name VARCHAR(100),
            avatar_url TEXT,
            phone VARCHAR(20),
            is_super_admin BOOLEAN NOT NULL DEFAULT false,
            is_tenant_admin BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ,
            UNIQUE (tenant_id, email)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE user_departments (
            user_id UUID NOT NULL REFERENCES users(id),
            department_id UUID NOT NULL REFERENCES departments(id),
            is_leader BOOLEAN NOT NULL DEFAULT false,
            is_primary BOOLEAN NOT NULL DEFAULT false,
            position_title VARCHAR(100),
            cost_center_id UUID REFERENCES cost_centers(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, department_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE roles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            name VARCHAR(50) NOT NULL,
            description TEXT,
            permissions JSONB NOT NULL DEFAULT '[]',
            is_system BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE user_roles (
            user_id UUID NOT NULL REFERENCES users(id),
            role_id UUID NOT NULL REFERENCES roles(id),
            granted_by UUID REFERENCES users(id),
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, role_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE resource_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            resource_type VARCHAR(50) NOT NULL,
            resource_id UUID NOT NULL,
            subject_type VARCHAR(20) NOT NULL,
            subject_id UUID NOT NULL,
            permissions JSONB NOT NULL DEFAULT '[]',
            conditions JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE agent_modules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            module_key VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL,
            priority VARCHAR(10) NOT NULL,
            description TEXT,
            version VARCHAR(30) NOT NULL,
            manifest JSONB NOT NULL DEFAULT '{}',
            is_official BOOLEAN NOT NULL DEFAULT true,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tenant_agent_modules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            module_id UUID NOT NULL REFERENCES agent_modules(id),
            state VARCHAR(30) NOT NULL DEFAULT 'not_installed',
            installed_by UUID REFERENCES users(id),
            installed_at TIMESTAMPTZ,
            enabled_at TIMESTAMPTZ,
            disabled_at TIMESTAMPTZ,
            config JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, module_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE licenses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            license_key_hash VARCHAR(128) NOT NULL,
            license_type VARCHAR(20) NOT NULL DEFAULT 'basic',
            customer_name VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'inactive',
            deployment_id UUID NOT NULL,
            install_id UUID NOT NULL,
            machine_fingerprint_hash VARCHAR(128) NOT NULL,
            allowed_modules JSONB NOT NULL DEFAULT '[]',
            allowed_features JSONB NOT NULL DEFAULT '[]',
            max_users INTEGER,
            max_agents INTEGER,
            maintenance_until TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            activated_at TIMESTAMPTZ,
            signature_payload JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE license_activations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            license_id UUID NOT NULL REFERENCES licenses(id),
            deployment_id UUID NOT NULL,
            install_id UUID NOT NULL,
            machine_fingerprint_hash VARCHAR(128) NOT NULL,
            activation_type VARCHAR(20) NOT NULL DEFAULT 'offline',
            status VARCHAR(20) NOT NULL,
            activated_by UUID REFERENCES users(id),
            activated_at TIMESTAMPTZ,
            deactivated_at TIMESTAMPTZ,
            request_payload JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_providers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            provider_key VARCHAR(80) NOT NULL,
            name VARCHAR(100) NOT NULL,
            adapter_type VARCHAR(40) NOT NULL,
            base_url TEXT,
            region VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT true,
            config JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, provider_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_credentials (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            provider_id UUID NOT NULL REFERENCES llm_providers(id),
            owner_type VARCHAR(20) NOT NULL DEFAULT 'tenant',
            owner_id UUID,
            display_name VARCHAR(100) NOT NULL,
            secret_ref VARCHAR(255) NOT NULL,
            masked_secret VARCHAR(80) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_rotated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_models (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_key VARCHAR(80) NOT NULL,
            model_key VARCHAR(120) NOT NULL UNIQUE,
            display_name VARCHAR(120) NOT NULL,
            model_type VARCHAR(30) NOT NULL DEFAULT 'chat',
            context_window INTEGER,
            capabilities JSONB NOT NULL DEFAULT '[]',
            is_global BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_deployments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            provider_id UUID NOT NULL REFERENCES llm_providers(id),
            model_id UUID NOT NULL REFERENCES llm_models(id),
            credential_id UUID REFERENCES llm_credentials(id),
            deployment_name VARCHAR(120) NOT NULL,
            routing_key VARCHAR(120) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            priority INTEGER NOT NULL DEFAULT 100,
            config JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (tenant_id, routing_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_model_prices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_id UUID NOT NULL REFERENCES llm_models(id),
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            input_per_1k_tokens NUMERIC(12,8) NOT NULL DEFAULT 0,
            output_per_1k_tokens NUMERIC(12,8) NOT NULL DEFAULT 0,
            effective_from TIMESTAMPTZ NOT NULL,
            effective_to TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_budgets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            scope_type VARCHAR(30) NOT NULL,
            scope_id UUID,
            period VARCHAR(20) NOT NULL DEFAULT 'monthly',
            amount_usd NUMERIC(12,4) NOT NULL DEFAULT 0,
            token_limit BIGINT,
            hard_limit BOOLEAN NOT NULL DEFAULT true,
            alert_threshold_pct INTEGER NOT NULL DEFAULT 80,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE conversation_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            title VARCHAR(160) NOT NULL,
            agent_id UUID,
            channel_id UUID,
            user_id UUID REFERENCES users(id),
            department_id UUID REFERENCES departments(id),
            source VARCHAR(40) NOT NULL DEFAULT 'chat_console',
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE conversation_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            conversation_id UUID NOT NULL REFERENCES conversation_sessions(id),
            role VARCHAR(40) NOT NULL,
            content TEXT NOT NULL,
            user_id UUID REFERENCES users(id),
            request_id VARCHAR(64),
            model_key VARCHAR(120),
            provider_key VARCHAR(80),
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE llm_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            deployment_id UUID REFERENCES llm_deployments(id),
            user_id UUID REFERENCES users(id),
            department_id UUID REFERENCES departments(id),
            agent_id UUID,
            channel_id UUID,
            conversation_id UUID REFERENCES conversation_sessions(id),
            request_id VARCHAR(64) NOT NULL,
            model_key VARCHAR(120) NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
            status VARCHAR(30) NOT NULL DEFAULT 'success',
            error_code VARCHAR(80),
            metadata_json JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            request_id VARCHAR(64),
            actor_id UUID REFERENCES users(id),
            actor_type VARCHAR(30) NOT NULL DEFAULT 'user',
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id UUID,
            status VARCHAR(30) NOT NULL DEFAULT 'success',
            ip_address VARCHAR(64),
            user_agent TEXT,
            details JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    _create_indexes()


def downgrade() -> None:
    for table in (
        "audit_logs",
        "llm_usage",
        "conversation_messages",
        "conversation_sessions",
        "llm_budgets",
        "llm_model_prices",
        "llm_deployments",
        "llm_models",
        "llm_credentials",
        "llm_providers",
        "license_activations",
        "licenses",
        "tenant_agent_modules",
        "agent_modules",
        "resource_permissions",
        "user_roles",
        "roles",
        "user_departments",
        "users",
        "cost_centers",
        "departments",
        "tenants",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def _create_indexes() -> None:
    index_sql: Sequence[str] = (
        "CREATE INDEX ix_departments_tenant_parent ON departments (tenant_id, parent_id)",
        "CREATE INDEX ix_users_tenant_active ON users (tenant_id, is_active)",
        "CREATE INDEX ix_resource_permissions_lookup ON resource_permissions "
        "(tenant_id, resource_type, resource_id, subject_type, subject_id)",
        "CREATE INDEX ix_tenant_agent_modules_state ON tenant_agent_modules (tenant_id, state)",
        "CREATE INDEX ix_licenses_tenant_status ON licenses (tenant_id, status)",
        "CREATE INDEX ix_license_activations_license ON license_activations (license_id, status)",
        "CREATE INDEX ix_llm_credentials_owner ON llm_credentials (tenant_id, owner_type, owner_id)",
        "CREATE INDEX ix_llm_deployments_active ON llm_deployments (tenant_id, is_active, priority)",
        "CREATE INDEX ix_llm_budgets_scope ON llm_budgets (tenant_id, scope_type, scope_id, period)",
        "CREATE INDEX ix_conversation_sessions_tenant ON conversation_sessions "
        "(tenant_id, updated_at, user_id, agent_id)",
        "CREATE INDEX ix_conversation_messages_session ON conversation_messages "
        "(tenant_id, conversation_id, created_at)",
        "CREATE INDEX ix_llm_usage_rollup ON llm_usage "
        "(tenant_id, created_at, department_id, user_id, model_key)",
        "CREATE INDEX ix_audit_logs_query ON audit_logs (tenant_id, created_at, action, status)",
    )
    for statement in index_sql:
        op.execute(statement)
