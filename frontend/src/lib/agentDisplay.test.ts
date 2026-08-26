import { describe, expect, it } from "vitest";
import { agentDisplayDescription, agentDisplayName, localizedTaskTitle } from "./agentDisplay";

describe("agentDisplayName", () => {
  it("returns the Chinese name for a known agent in zh-CN", () => {
    const result = agentDisplayName({ agent_key: "copywriting", name: "Copywriting Agent" }, "zh-CN");
    expect(result).toBe("文案创作助手");
  });

  it("returns the English name for a known agent in en-US", () => {
    const result = agentDisplayName({ agent_key: "copywriting", name: "Original Name" }, "en-US");
    expect(result).toBe("Copywriting Agent");
  });

  it("falls back to agent.name for an unknown agent_key in zh-CN", () => {
    const result = agentDisplayName({ agent_key: "unknown_key", name: "Fallback Name" }, "zh-CN");
    expect(result).toBe("Fallback Name");
  });

  it("falls back to agent.name for an unknown agent_key in en-US", () => {
    const result = agentDisplayName({ agent_key: "unknown_key", name: "Fallback Name" }, "en-US");
    expect(result).toBe("Fallback Name");
  });

  it("provides localized names for every registered agent key", () => {
    const keys = [
      "content_analysis",
      "copywriting",
      "customer_service",
      "data_analyst",
      "finance",
      "hr_screening",
      "image_generation",
      "product_design",
      "report_writer",
      "store_operations",
      "video_generation",
    ];
    for (const key of keys) {
      const zh = agentDisplayName({ agent_key: key, name: "fallback" }, "zh-CN");
      const en = agentDisplayName({ agent_key: key, name: "fallback" }, "en-US");
      expect(zh).not.toBe("fallback");
      expect(en).not.toBe("fallback");
      expect(typeof zh).toBe("string");
      expect(typeof en).toBe("string");
      expect(zh).not.toBe(en);
    }
  });
});

describe("agentDisplayDescription", () => {
  it("returns the Chinese description for a known agent in zh-CN", () => {
    const result = agentDisplayDescription({ agent_key: "finance", name: "x" }, "zh-CN");
    expect(result).toContain("财务");
  });

  it("returns the English description for a known agent in en-US", () => {
    const result = agentDisplayDescription({ agent_key: "finance", name: "x" }, "en-US");
    expect(result).toContain("finance");
  });

  it("falls back to agent.description when agent_key is unknown", () => {
    const result = agentDisplayDescription(
      { agent_key: "unknown", name: "x", description: "Custom description" },
      "zh-CN",
    );
    expect(result).toBe("Custom description");
  });

  it("falls back to undefined when description is missing and agent_key is unknown", () => {
    const result = agentDisplayDescription({ agent_key: "unknown", name: "x" }, "en-US");
    expect(result).toBeUndefined();
  });

  it("falls back to null when description is null and agent_key is unknown", () => {
    const result = agentDisplayDescription({ agent_key: "unknown", name: "x", description: null }, "en-US");
    expect(result).toBeNull();
  });
});

describe("localizedTaskTitle", () => {
  it("returns the original title for en-US locale", () => {
    expect(localizedTaskTitle("readiness smoke test", "en-US")).toBe("readiness smoke test");
    expect(localizedTaskTitle("anything goes here", "en-US")).toBe("anything goes here");
  });

  it("translates the 'readiness smoke' prefix in zh-CN", () => {
    expect(localizedTaskTitle("readiness smoke check", "zh-CN")).toBe("就绪验证");
  });

  it("translates 'codex smoke test clean answer' in zh-CN", () => {
    expect(localizedTaskTitle("codex smoke test clean answer 123", "zh-CN")).toBe("回复清洗验证");
  });

  it("translates 'codex smoke test final' in zh-CN", () => {
    expect(localizedTaskTitle("codex smoke test final", "zh-CN")).toBe("最终联调验证");
  });

  it("translates a generic 'codex smoke test' prefix in zh-CN", () => {
    expect(localizedTaskTitle("codex smoke test abc", "zh-CN")).toBe("联调验证");
  });

  it("replaces the 'Smoke check' prefix in zh-CN while keeping the suffix", () => {
    expect(localizedTaskTitle("Smoke check for onboarding", "zh-CN")).toBe("验收测试 for onboarding");
  });

  it("replaces 'E-commerce Customer Service Agent' occurrences in zh-CN", () => {
    const result = localizedTaskTitle("Run E-commerce Customer Service Agent now", "zh-CN");
    expect(result).toContain("电商客服助手");
    expect(result).not.toContain("E-commerce Customer Service Agent");
  });

  it("replaces 'HR Resume Screening Agent' occurrences in zh-CN", () => {
    const result = localizedTaskTitle("HR Resume Screening Agent daily", "zh-CN");
    expect(result).toContain("人事简历筛选助手");
    expect(result).not.toContain("HR Resume Screening Agent");
  });

  it("returns the title unchanged in zh-CN when no pattern matches", () => {
    expect(localizedTaskTitle("Quarterly business review", "zh-CN")).toBe("Quarterly business review");
  });
});
