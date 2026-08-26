import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "../../i18n-context";
import type { LLMConnectionTestResponse } from "../../lib/api";
import { CredentialDiagnosticsPanel } from "./CredentialDiagnosticsPanel";
import type { CredentialFormState } from "./modelUtils";

const credentialForm: CredentialFormState = {
  apiKey: "",
  baseUrl: "https://provider.example.test",
  deploymentName: "Demo deployment",
  displayName: "Demo provider",
  modelKey: "demo-model",
  ownerId: "",
  ownerType: "tenant",
  probePath: "/models",
  routingKey: "default-chat",
};

const failedResult: LLMConnectionTestResponse = {
  adapter_type: "openai_compatible",
  checked_at: "2026-08-26T00:00:00Z",
  diagnostics: {
    live_network_call: true,
    route_attempts: [
      {
        error_message: "ECONNREFUSED 10.0.0.7:443",
        provider_key: "demo",
        status: "failed",
      },
    ],
    status_code: 502,
  },
  latency_ms: 120,
  message: "upstream socket closed before response headers",
  model_key: "demo-model",
  ok: false,
  provider_key: "demo",
};

describe("CredentialDiagnosticsPanel", () => {
  it("replaces raw probe transport errors with actionable readiness guidance", () => {
    render(
      <LocaleProvider locale="en-US" setLocale={() => undefined}>
        <CredentialDiagnosticsPanel
          canWrite
          credentialForm={credentialForm}
          isMedia
          lastAcceptanceResult={null}
          lastTestResult={failedResult}
          onAcceptanceTest={() => undefined}
          onLiveProbe={() => undefined}
          onTestConnection={() => undefined}
          setCredentialForm={() => undefined}
          testing={false}
        />
      </LocaleProvider>,
    );

    expect(screen.getAllByText("端点未能成功响应。请检查 Base URL、模型 Key 和凭据后重试。")).toHaveLength(2);
    expect(screen.queryByText("upstream socket closed before response headers")).not.toBeInTheDocument();
    expect(screen.queryByText("ECONNREFUSED 10.0.0.7:443")).not.toBeInTheDocument();
  });
});
