import { describe, expect, it } from "vitest";
import {
  type BuilderFormState,
  configToForm,
  deriveRuntimeHints,
  emptyBuilderForm,
  formToConfig,
  issueSeverityLabel,
} from "./builderUtils";

describe("formToConfig", () => {
  it("returns minimal config for empty form", () => {
    // Override smart defaults to verify truly-empty form behaviour
    const empty = { ...emptyBuilderForm, temperature: "", max_tokens: "", confidence_threshold: "" };
    const config = formToConfig(empty);
    expect(config.name).toBe("");
    expect(config.system_prompt).toBe("");
    expect(config.response_style).toBe("formal");
    expect(config.language).toBe("auto");
    expect(config.description).toBeUndefined();
    expect(config.deployment_id).toBeUndefined();
    expect(config.temperature).toBeUndefined();
  });

  it("trims name and description", () => {
    const config = formToConfig({
      ...emptyBuilderForm,
      name: "  HR Bot  ",
      description: "  desc  ",
    });
    expect(config.name).toBe("HR Bot");
    expect(config.description).toBe("desc");
  });

  it("converts numeric strings to numbers, ignores NaN", () => {
    const config = formToConfig({
      ...emptyBuilderForm,
      temperature: "0.7",
      max_tokens: "1024",
      max_cost_per_request: "0.05",
    });
    expect(config.temperature).toBe(0.7);
    expect(config.max_tokens).toBe(1024);
    expect(config.max_cost_per_request).toBe(0.05);
  });

  it("ignores invalid numeric strings", () => {
    const config = formToConfig({
      ...emptyBuilderForm,
      temperature: "abc",
      max_tokens: "",
    });
    expect(config.temperature).toBeUndefined();
    expect(config.max_tokens).toBeUndefined();
  });

  it("includes escalation_message only when confidence_threshold is set", () => {
    const withBoth = formToConfig({
      ...emptyBuilderForm,
      confidence_threshold: "0.6",
      escalation_message: "Please transfer to a human",
    });
    expect(withBoth.confidence_threshold).toBe(0.6);
    expect(withBoth.escalation_message).toBe("Please transfer to a human");

    const withMessageOnly = formToConfig({
      ...emptyBuilderForm,
      confidence_threshold: "",
      escalation_message: "orphan message",
    });
    // escalation_message is dropped when confidence_threshold is not set
    expect(withMessageOnly.escalation_message).toBeUndefined();
  });

  it("filters empty strings from fallback_deployment_ids", () => {
    const config = formToConfig({
      ...emptyBuilderForm,
      fallback_deployment_ids: ["  ", "dep1", "", "dep2"],
    });
    expect(config.fallback_deployment_ids).toEqual(["dep1", "dep2"]);
  });
});

describe("configToForm", () => {
  it("round-trips through formToConfig (numeric fields become strings)", () => {
    const original: BuilderFormState = {
      ...emptyBuilderForm,
      name: "Test",
      description: "desc",
      deployment_id: "dep-1",
      temperature: "0.5",
      max_tokens: "512",
      confidence_threshold: "0.8",
      escalation_message: "escalate",
      knowledge_base_ids: ["kb1"],
    };
    const config = formToConfig(original);
    const roundTripped = configToForm(config);
    expect(roundTripped.name).toBe("Test");
    expect(roundTripped.description).toBe("desc");
    expect(roundTripped.deployment_id).toBe("dep-1");
    expect(roundTripped.temperature).toBe("0.5");
    expect(roundTripped.max_tokens).toBe("512");
    expect(roundTripped.confidence_threshold).toBe("0.8");
    expect(roundTripped.escalation_message).toBe("escalate");
    expect(roundTripped.knowledge_base_ids).toEqual(["kb1"]);
  });

  it("substitutes defaults for missing fields", () => {
    const form = configToForm({
      name: "X",
      system_prompt: "Y",
      response_style: "formal",
      language: "auto",
    });
    expect(form.name).toBe("X");
    expect(form.response_style).toBe("formal");
    expect(form.language).toBe("auto");
    expect(form.temperature).toBe("");
    expect(form.fallback_deployment_ids).toEqual([]);
  });
});

describe("issueSeverityLabel", () => {
  it("returns English labels for en-US", () => {
    expect(issueSeverityLabel("error", "en-US")).toBe("Error");
    expect(issueSeverityLabel("warning", "en-US")).toBe("Warning");
  });

  it("returns Chinese labels for zh-CN", () => {
    expect(issueSeverityLabel("error", "zh-CN")).toBe("错误");
    expect(issueSeverityLabel("warning", "zh-CN")).toBe("警告");
  });
});

describe("deriveRuntimeHints", () => {
  it("flags missing routing target", () => {
    const hints = deriveRuntimeHints({ ...emptyBuilderForm }, "en-US");
    expect(hints.some((h) => h.field === "deployment_id")).toBe(true);
  });

  it("does not flag routing target when deployment_id is set", () => {
    const hints = deriveRuntimeHints({ ...emptyBuilderForm, deployment_id: "dep-1" }, "en-US");
    expect(hints.some((h) => h.field === "deployment_id")).toBe(false);
  });

  it("flags escalation_message missing when confidence_threshold is set", () => {
    const hints = deriveRuntimeHints(
      { ...emptyBuilderForm, deployment_id: "dep-1", confidence_threshold: "0.7" },
      "en-US",
    );
    const escalationHint = hints.find((h) => h.field === "escalation_message");
    expect(escalationHint).toBeDefined();
  });

  it("flags confidence_threshold out of range", () => {
    const hints = deriveRuntimeHints(
      {
        ...emptyBuilderForm,
        deployment_id: "dep-1",
        confidence_threshold: "1.5",
        escalation_message: "msg",
      },
      "en-US",
    );
    const rangeHint = hints.find(
      (h) => h.field === "confidence_threshold" && h.message.toLowerCase().includes("between"),
    );
    expect(rangeHint).toBeDefined();
  });

  it("returns no hints for a fully valid minimal form", () => {
    const hints = deriveRuntimeHints(
      {
        ...emptyBuilderForm,
        deployment_id: "dep-1",
        confidence_threshold: "0.5",
        escalation_message: "escalate",
      },
      "en-US",
    );
    expect(hints).toHaveLength(0);
  });

  it("returns Chinese messages for zh-CN locale", () => {
    const hints = deriveRuntimeHints({ ...emptyBuilderForm }, "zh-CN");
    expect(hints.some((h) => /至少需要/.test(h.message))).toBe(true);
  });
});
