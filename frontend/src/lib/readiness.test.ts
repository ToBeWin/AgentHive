import { describe, expect, it, vi } from "vitest";
import {
  readinessReasonAdminAction,
  readinessReasonEmployeeImpact,
  readinessReasonLabel,
  readinessReasonLabels,
  uniqueReadinessReasons,
} from "./readiness";

describe("readinessReasonLabel", () => {
  it("returns the model missing label for 'model_policy_not_configured'", () => {
    const t = vi.fn((key: string) => key);
    const result = readinessReasonLabel("model_policy_not_configured", t);
    expect(result).toBe("agentReadinessReasonModelMissing");
    expect(t).toHaveBeenCalledWith("agentReadinessReasonModelMissing");
  });

  it("returns the model route unavailable label", () => {
    const t = (key: string) => key;
    expect(readinessReasonLabel("model_route_unavailable", t)).toBe("agentReadinessReasonModelRouteUnavailable");
  });

  it("returns the model unavailable label", () => {
    const t = (key: string) => key;
    expect(readinessReasonLabel("model_unavailable", t)).toBe("agentReadinessReasonModelUnavailable");
  });

  it("returns the knowledge missing label", () => {
    const t = (key: string) => key;
    expect(readinessReasonLabel("knowledge_not_bound", t)).toBe("agentReadinessReasonKnowledgeMissing");
  });

  it("returns the not active label", () => {
    const t = (key: string) => key;
    expect(readinessReasonLabel("agent_not_active", t)).toBe("agentReadinessReasonNotActive");
  });

  it("returns the unknown label for unrecognized reasons", () => {
    const t = vi.fn((key: string) => key);
    expect(readinessReasonLabel("some_random_reason", t)).toBe("agentReadinessReasonUnknown");
    expect(readinessReasonLabel("", t)).toBe("agentReadinessReasonUnknown");
  });
});

describe("readinessReasonLabels", () => {
  it("maps each reason to its corresponding label", () => {
    const t = (key: string) => key;
    const result = readinessReasonLabels(["model_policy_not_configured", "agent_not_active", "unknown_reason"], t);
    expect(result).toEqual([
      "agentReadinessReasonModelMissing",
      "agentReadinessReasonNotActive",
      "agentReadinessReasonUnknown",
    ]);
  });

  it("returns an empty array for empty input", () => {
    expect(readinessReasonLabels([], () => "x")).toEqual([]);
  });
});

describe("readinessReasonEmployeeImpact", () => {
  it("returns the impact text for each known reason", () => {
    const t = (key: string) => key;
    expect(readinessReasonEmployeeImpact("model_policy_not_configured", t)).toBe(
      "agentReadinessEmployeeImpactModelMissing",
    );
    expect(readinessReasonEmployeeImpact("model_route_unavailable", t)).toBe(
      "agentReadinessEmployeeImpactModelRouteUnavailable",
    );
    expect(readinessReasonEmployeeImpact("model_unavailable", t)).toBe("agentReadinessEmployeeImpactModelUnavailable");
    expect(readinessReasonEmployeeImpact("knowledge_not_bound", t)).toBe(
      "agentReadinessEmployeeImpactKnowledgeMissing",
    );
    expect(readinessReasonEmployeeImpact("agent_not_active", t)).toBe("agentReadinessEmployeeImpactNotActive");
  });

  it("returns the unknown impact for an unrecognized reason", () => {
    const t = (key: string) => key;
    expect(readinessReasonEmployeeImpact("weird", t)).toBe("agentReadinessEmployeeImpactUnknown");
  });
});

describe("readinessReasonAdminAction", () => {
  it("returns the admin action text for each known reason", () => {
    const t = (key: string) => key;
    expect(readinessReasonAdminAction("model_policy_not_configured", t)).toBe("agentReadinessAdminActionModelMissing");
    expect(readinessReasonAdminAction("model_route_unavailable", t)).toBe(
      "agentReadinessAdminActionModelRouteUnavailable",
    );
    expect(readinessReasonAdminAction("model_unavailable", t)).toBe("agentReadinessAdminActionModelUnavailable");
    expect(readinessReasonAdminAction("knowledge_not_bound", t)).toBe("agentReadinessAdminActionKnowledgeMissing");
    expect(readinessReasonAdminAction("agent_not_active", t)).toBe("agentReadinessAdminActionNotActive");
  });

  it("returns the unknown admin action for an unrecognized reason", () => {
    const t = (key: string) => key;
    expect(readinessReasonAdminAction("???", t)).toBe("agentReadinessAdminActionUnknown");
  });
});

describe("uniqueReadinessReasons", () => {
  it("removes duplicates while preserving insertion order", () => {
    const result = uniqueReadinessReasons([
      "model_unavailable",
      "model_unavailable",
      "agent_not_active",
      "model_unavailable",
    ]);
    expect(result).toEqual(["model_unavailable", "agent_not_active"]);
  });

  it("filters out empty strings", () => {
    const result = uniqueReadinessReasons(["", "model_unavailable", ""]);
    expect(result).toEqual(["model_unavailable"]);
  });

  it("returns an empty array for empty input", () => {
    expect(uniqueReadinessReasons([])).toEqual([]);
  });

  it("returns an empty array when all values are falsy", () => {
    expect(uniqueReadinessReasons(["", ""])).toEqual([]);
  });

  it("preserves a single-element array", () => {
    expect(uniqueReadinessReasons(["agent_not_active"])).toEqual(["agent_not_active"]);
  });
});
