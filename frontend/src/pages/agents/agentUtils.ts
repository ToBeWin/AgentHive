import type { AgentCatalogEntryResponse } from "../../lib/api";

export function formatLicenseGate(agent: AgentCatalogEntryResponse, t: (key: string) => string) {
  if (agent.license_gate !== "enforced") {
    return agent.license_gate.replace(/_/g, " ").toUpperCase();
  }
  if (agent.enabled) {
    return t("agentsEnabled");
  }
  return agent.licensed ? t("agentsNotEnabled") : t("agentsNotLicensed");
}

export function formatLicenseGateDetail(agent: AgentCatalogEntryResponse, t: (key: string) => string) {
  if (agent.license_gate !== "enforced") {
    return agent.license_gate.replace(/_/g, " ");
  }
  return `${t("agentsLicensed")}: ${agent.licensed ? t("agentsYes") : t("agentsNo")} · ${t("agentsInstalledField")}: ${
    agent.installed ? t("agentsYes") : t("agentsNo")
  } · ${t("agentsEnabledField")}: ${agent.enabled ? t("agentsYes") : t("agentsNo")}`;
}

export function sourceKey(source: Record<string, unknown>) {
  return String(
    source.chunk_id ??
      `${String(source.knowledge_base_id ?? "")}-${String(source.document_id ?? "")}-${String(
        source.source_name ?? "",
      )}`,
  );
}

export function sourceLabel(source: Record<string, unknown>) {
  const sourceName = String(source.source_name ?? source.document_id ?? source.chunk_id ?? "source");
  const knowledgeBaseName = typeof source.knowledge_base_name === "string" ? source.knowledge_base_name : "";
  return knowledgeBaseName ? `${knowledgeBaseName} / ${sourceName}` : sourceName;
}

export function isMediaAgent(agent: AgentCatalogEntryResponse) {
  return agent.orchestration_runtime === "media_gateway";
}

export function mediaRoutingKey(agentKey: string) {
  if (agentKey === "image_generation") {
    return "image-generation";
  }
  if (agentKey === "video_generation") {
    return "video-generation";
  }
  return "default-chat";
}

export function mediaRunContext(agentKey: string): Record<string, unknown> {
  if (agentKey === "image_generation") {
    return {
      media_mode: "natural_language",
      media_dispatch_mode: "enqueue",
      image_count: 1,
      aspect_ratio: "1:1",
      resolution: "1024x1024",
    };
  }
  if (agentKey === "video_generation") {
    return {
      media_mode: "natural_language",
      media_dispatch_mode: "enqueue",
      duration_seconds: 5,
      fps: 24,
      resolution: "1080p",
    };
  }
  return {};
}
