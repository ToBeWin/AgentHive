import type { SystemHealthReport, SystemInfoResponse } from "../../lib/api";
import type { getPrototypeSnapshot } from "./prototypeState";

type PrototypeSnapshot = ReturnType<typeof getPrototypeSnapshot>;

const PROTOTYPE_CHECKED_AT = "2026-01-01T00:00:00.000Z";

export function prototypeSystemDiagnostics(snapshot: PrototypeSnapshot) {
  const readiness = prototypeReadinessReport(snapshot);
  return {
    connection_acceptance: prototypeConnectionAcceptanceEvidence(),
    health: prototypeHealthReport(),
    info: prototypeSystemInfo(),
    knowledge_acceptance: prototypeKnowledgeAcceptanceEvidence(snapshot),
    readiness,
  };
}

function prototypeSystemInfo(): SystemInfoResponse {
  return {
    edition: "private-deployment",
    name: "AgentHive",
    version: "0.1.0-prototype",
  };
}

function prototypeHealthReport(): SystemHealthReport {
  return {
    checked_at: PROTOTYPE_CHECKED_AT,
    components: {
      database: {
        checked_at: PROTOTYPE_CHECKED_AT,
        component: "postgresql",
        details: {
          business_database: "PostgreSQL 16",
          migration_state: "current",
          tenant_count: 1,
        },
        message: "PostgreSQL business database is reachable in Prototype Mode.",
        status: "healthy",
      },
      license_identity: licenseIdentityComponent(),
      minio: {
        checked_at: PROTOTYPE_CHECKED_AT,
        component: "minio",
        details: {
          bucket_count: 3,
          default_bucket: "agenthive-knowledge",
          object_storage_boundary: "private_minio",
        },
        message: "MinIO object storage boundary is configured.",
        status: "healthy",
      },
      production_config: productionConfigComponent(),
      redis: {
        checked_at: PROTOTYPE_CHECKED_AT,
        component: "redis",
        details: {
          broker: "redis://redis:6379/0",
          cache_namespace: "agenthive",
          queue_runtime: "celery",
        },
        message: "Redis cache and queue runtime are reachable.",
        status: "healthy",
      },
    },
    environment: "prototype",
    service: "agenthive-backend",
    status: "healthy",
    version: "0.1.0-prototype",
  };
}

function prototypeConnectionAcceptanceEvidence() {
  return {
    failed_recent_count: 0,
    latest_live_probe: {
      checked_at: PROTOTYPE_CHECKED_AT,
      configuration_source: "tenant_credential",
      latency_ms: 186,
      live_network_call: true,
      model_key: "qwen-plus",
      ok: true,
      operation: "model_connection_check",
      probe_path: null,
      provider_key: "qwen",
      provider_type: "openai_compatible",
      selected_route_reason: "department policy matched Customer Success",
      status: "success",
      status_code: null,
    },
    latest_media_live_probe: {
      checked_at: PROTOTYPE_CHECKED_AT,
      configuration_source: "tenant_credential",
      latency_ms: 72,
      live_network_call: true,
      model_key: "google/nano-banana",
      ok: true,
      operation: "media_provider_live_probe",
      probe_path: "/models",
      provider_key: "nano_banana",
      provider_type: "nano_banana",
      selected_route_reason: "media_provider_configuration",
      status: "success",
      status_code: 200,
    },
    live_network_call_count: 3,
    media_live_probe_count: 2,
    providers: ["qwen", "nano_banana", "volcengine_seedance"],
    recent_test_count: 4,
    recent_tests: [],
    status: "healthy",
    summary: "3 live provider network call(s) are recorded; 2 media provider live probe(s) are included.",
  };
}

function prototypeKnowledgeAcceptanceEvidence(snapshot: PrototypeSnapshot) {
  const indexedBaseIds = snapshot.knowledgeBases.map((base) => base.id).slice(0, 2);
  return {
    agents: ["customer_service", "copywriting"],
    guardrail_triggered_count: 0,
    human_review_required_count: 0,
    knowledge_enabled_run_count: 3,
    latest_knowledge_run: {
      agent_instance_id: snapshot.agentInstances[0]?.id ?? null,
      agent_instance_name: snapshot.agentInstances[0]?.name ?? "售后客服",
      agent_key: "customer_service",
      checked_at: PROTOTYPE_CHECKED_AT,
      confidence_level: "high",
      guardrail_mode: "strict",
      guardrail_triggered: false,
      knowledge_base_ids: indexedBaseIds,
      knowledge_enabled: true,
      max_score: 0.91,
      min_score: 0.86,
      model_key: "qwen-plus",
      required_module: "agent.customer_service",
      requires_human_review: false,
      review_reason: "strong_source_match",
      routing_key: "customer-service-route",
      skipped_model_call: false,
      source_count: 2,
      status: "success",
    },
    recent_run_count: 4,
    recent_runs: [],
    runs_with_sources_count: 3,
    status: "healthy",
    summary: "3 knowledge-enabled Agent run(s) are recorded; 3 run(s) returned cited knowledge sources.",
  };
}

function prototypeReadinessReport(snapshot: PrototypeSnapshot): SystemHealthReport {
  const components: SystemHealthReport["components"] = {
    audit_diagnostics: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "audit",
      details: {
        diagnostics_export: true,
        redaction_enabled: true,
        system_diagnostics_permission: "system:diagnostics",
      },
      message: "Audit log export and diagnostics redaction are ready.",
      status: "healthy",
    },
    agent_concurrency: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "agent_concurrency",
      details: {
        active_slot_count: 2,
        agent_limit: 12,
        enabled: true,
        tenant_limit: 40,
        user_limit: 4,
      },
      message: "Agent concurrency guard is enabled for tenant, user, and Agent execution slots.",
      status: "healthy",
    },
    budget_governance: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "budget",
      details: {
        cost_center_scope: "Customer Success",
        ledger_export: true,
        monthly_budget_usd: "2500.0000",
        pre_call_guard: true,
      },
      message: "Model budget guardrails and cost ledgers are configured.",
      status: "healthy",
    },
    channel_gateway: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "channel_gateway",
      details: {
        active_channels: snapshot.channels.filter((channel) => channel.status === "active").length,
        configured_channels: snapshot.channels.length,
        supported_channels: ["web_widget", "wecom", "dingtalk", "feishu", "rest_api"],
      },
      message: "Unified Channel Gateway has routable channels.",
      status: snapshot.channels.length > 0 ? "healthy" : "degraded",
    },
    database: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "postgresql",
      details: {
        business_database: "PostgreSQL 16",
        core_tables: ["tenants", "users", "agent_instances", "knowledge_bases", "llm_usage_ledger"],
        migration_state: "current",
      },
      message: "PostgreSQL is the authoritative business database.",
      status: "healthy",
    },
    frontend: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "vite/nginx",
      details: {
        console: "AgentHive management console",
        i18n: ["zh-CN", "en-US"],
        mode: "prototype_artifact_check",
      },
      message: "Management console is available and localized.",
      status: "healthy",
    },
    knowledge_runtime: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "rag",
      details: {
        indexed_documents: snapshot.knowledgeDocuments.filter((document) => document.status === "indexed").length,
        knowledge_bases: snapshot.knowledgeBases.length,
        object_storage: "MinIO",
        vector_store: "PostgreSQL + pgvector",
      },
      message: "Knowledge bases are indexed and ready for Agent binding.",
      status: snapshot.knowledgeDocuments.length > 0 ? "healthy" : "degraded",
    },
    license_identity: licenseIdentityComponent(),
    litellm: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "llm_gateway",
      details: {
        adapter: "LiteLLM + OpenAI-compatible",
        configured_routes: ["cn-primary-chat", "premium-chat", "cost-chat", "long-context-chat"],
        providers: ["OpenAI", "Claude", "Gemini", "Qwen", "DeepSeek", "Kimi", "MiniMax", "GLM", "Ollama"],
      },
      message: "AgentHive LLM Gateway has multi-model routes configured.",
      status: "healthy",
    },
    minio: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "minio",
      details: {
        buckets: ["agenthive-knowledge", "agenthive-exports", "agenthive-channel-attachments"],
        long_term_local_disk_storage: false,
      },
      message: "Uploaded files and exports are stored through MinIO.",
      status: "healthy",
    },
    pgvector: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "pgvector",
      details: {
        fallback_vector_store: true,
        retrieval_mode: "vector_similarity",
        schema_ready: true,
      },
      message: "pgvector retrieval fallback is ready.",
      status: "healthy",
    },
    production_config: productionConfigComponent(),
    redis: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "redis",
      details: {
        cache: true,
        queue: "celery",
        rate_limit: true,
      },
      message: "Redis runtime dependencies are ready.",
      status: "healthy",
    },
    ragflow: {
      checked_at: PROTOTYPE_CHECKED_AT,
      component: "ragflow",
      details: {
        engine_optional: true,
        fallback_engine: "pgvector",
        tenant_engine_routing: true,
      },
      message: "RAGFlow is optional; pgvector fallback remains available.",
      remediation: {
        action: "Configure RAGFLOW_URL only for tenants that require RAGFlow workflows.",
        docs_anchor: "deployment.ragflow",
        summary: "RAGFlow is not required for the default private deployment.",
      },
      status: "degraded",
    },
  };
  const delivery = buildPrototypeDelivery(components, snapshot);
  return {
    checked_at: PROTOTYPE_CHECKED_AT,
    components,
    delivery,
    environment: "prototype",
    service: "agenthive-backend",
    status: "healthy",
    version: "0.1.0-prototype",
  };
}

function licenseIdentityComponent(): SystemHealthReport["components"][string] {
  return {
    checked_at: PROTOTYPE_CHECKED_AT,
    component: "license_identity",
    details: {
      activation_mode: "offline",
      deployment_id: "00000000-0000-4000-8000-000000000501",
      install_id: "00000000-0000-4000-8000-000000000502",
      machine_fingerprint_hash: "sha256:88f1...e1e2",
      max_activations: 1,
    },
    message: "License identity is bound to this private deployment.",
    status: "healthy",
  };
}

function productionConfigComponent(): SystemHealthReport["components"][string] {
  return {
    checked_at: PROTOTYPE_CHECKED_AT,
    component: "production_config",
    details: {
      default_secrets_detected: false,
      environment: "prototype",
      private_deployment_ready: true,
      redaction_enabled: true,
    },
    message: "Production secret and config guardrails are satisfied for the prototype package.",
    status: "healthy",
  };
}

function buildPrototypeDelivery(components: SystemHealthReport["components"], snapshot: PrototypeSnapshot) {
  const warningCheck = {
    component: "ragflow",
    id: "ragflow",
    label: "Optional RAGFlow integration",
    message: "RAGFlow is not configured in Prototype Mode; pgvector fallback is ready.",
    remediation: components.ragflow.remediation ?? null,
    severity: "warning" as const,
    status: components.ragflow.status,
  };
  const passChecks = Object.entries(components)
    .filter(([key]) => key !== "ragflow")
    .map(([key, component]) => ({
      component: key,
      id: key,
      label: deliveryLabel(key),
      message: component.message ?? "",
      remediation: null,
      severity: "pass" as const,
      status: component.status,
    }));
  return {
    blocker_count: 0,
    blockers: [],
    checks: [
      ...passChecks,
      warningCheck,
      {
        component: "agent_runtime",
        id: "agent_runtime",
        label: "Agent runtime package",
        message: `${snapshot.agentInstances.length} Agent instance(s), ${snapshot.agentModules.filter((module) => module.enabled).length} enabled module(s), and ${snapshot.knowledgeBases.length} knowledge base(s) are available.`,
        remediation: null,
        severity: "pass" as const,
        status: "healthy",
      },
    ],
    status: "ready_with_warnings" as const,
    summary: "Deployment is usable for customer handoff; review optional RAGFlow integration only if required.",
    warning_count: 1,
    warnings: [warningCheck],
  };
}

function deliveryLabel(key: string) {
  const labels: Record<string, string> = {
    channel_gateway: "Unified Channel Gateway",
    audit_diagnostics: "Audit and diagnostics export",
    budget_governance: "Model budget governance",
    database: "PostgreSQL business database",
    frontend: "AgentHive management console",
    knowledge_runtime: "Knowledge and RAG runtime",
    license_identity: "License install identity",
    litellm: "LiteLLM model gateway adapter",
    minio: "MinIO object storage",
    pgvector: "PostgreSQL pgvector retrieval store",
    production_config: "Production secret and config gate",
    redis: "Redis cache and queue runtime",
  };
  return labels[key] ?? key.replace(/_/g, " ");
}
