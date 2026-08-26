import { describe, expect, it } from "vitest";
import * as apiModule from "./api";

describe("api barrel export", () => {
  it("re-exports all API modules", () => {
    const exportedKeys = Object.keys(apiModule).sort();
    expect(exportedKeys.length).toBeGreaterThan(20);
    expect(exportedKeys).toContain("chatApi");
    expect(exportedKeys).toContain("agentsApi");
    expect(exportedKeys).toContain("knowledgeApi");
    expect(exportedKeys).toContain("modelsApi");
    expect(exportedKeys).toContain("adminApi");
    expect(exportedKeys).toContain("authApi");
    expect(exportedKeys).toContain("channelsApi");
    expect(exportedKeys).toContain("budgetsApi");
    expect(exportedKeys).toContain("mediaApi");
    expect(exportedKeys).toContain("auditApi");
    expect(exportedKeys).toContain("builderApi");
    expect(exportedKeys).toContain("licenseApi");
    expect(exportedKeys).toContain("mcpApi");
    expect(exportedKeys).toContain("analyticsApi");
    expect(exportedKeys).toContain("systemApi");
    expect(exportedKeys).toContain("orgApi");
  });
});
