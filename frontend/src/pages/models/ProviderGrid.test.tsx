import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n-context";
import type { LLMProviderResponse } from "../../lib/api";
import { ProviderGrid } from "./ProviderGrid";
import { resolveProviderReadiness } from "./ProviderReadinessSummary";

const provider = (overrides: Partial<LLMProviderResponse> = {}): LLMProviderResponse => ({
  adapter_type: "openai_compatible",
  base_url: null,
  capabilities: ["chat"],
  credential_configured: false,
  metadata: {},
  name: "Demo provider",
  provider_key: "demo",
  region: null,
  status: "active",
  ...overrides,
});

describe("ProviderGrid empty state", () => {
  it("explains the next configuration step when no providers are registered", () => {
    const { container } = render(
      <LocaleProvider locale="zh-CN" setLocale={vi.fn()}>
        <ProviderGrid
          providersError={"TypeError: Failed to fetch /api/v1/models/providers"}
          providersList={[]}
          providersLoading={false}
          refetchProviders={vi.fn()}
          selectedProviderKey={null}
          setSelectedProviderKey={vi.fn()}
        />
      </LocaleProvider>,
    );

    expect(screen.getByText("还没有注册模型供应商。")).toBeInTheDocument();
    expect(screen.getByText("请先通过页面上方添加端点，再继续配置范围化凭据。")).toBeInTheDocument();
    expect(screen.queryByText("TypeError: Failed to fetch /api/v1/models/providers")).not.toBeInTheDocument();
    expect(container.querySelector(".provider-empty-state")).toBeInTheDocument();
  });
});

describe("provider readiness states", () => {
  it.each([
    ["configured", provider({ credential_configured: true }), undefined, false],
    ["unavailable", provider({ status: "inactive" }), undefined, false],
    ["testing", provider({ credential_configured: true }), undefined, true],
    ["success", provider({ credential_configured: true }), { ok: true }, false],
    ["failure", provider({ credential_configured: true }), { ok: false }, false],
    ["not-configured", provider(), undefined, false],
  ] as const)("resolves %s", (kind, currentProvider, testResult, testing) => {
    const readiness = resolveProviderReadiness({
      lastTestResult: testResult
        ? {
            adapter_type: "openai_compatible",
            checked_at: "2026-08-26T00:00:00Z",
            diagnostics: {},
            latency_ms: 120,
            message: "raw transport detail",
            model_key: "demo-model",
            ok: testResult.ok,
            provider_key: currentProvider.provider_key,
          }
        : null,
      provider: currentProvider,
      testing,
    });

    expect(readiness.kind).toBe(kind);
  });
});
