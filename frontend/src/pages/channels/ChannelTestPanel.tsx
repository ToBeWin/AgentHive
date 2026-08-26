import { SendHorizontal } from "lucide-react";
import { useState } from "react";
import { Button, cx, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChannelProcessingResult, InboundMessageResponse } from "../../lib/api";
import { type ChannelFormState, formatProcessingMessage } from "./channelUtils";

type ChannelTestResultTab = "normalized" | "routing" | "evidence";

export function ChannelTestPanel({
  canWrite,
  form,
  onFormChange,
  onTest,
  selected,
  testProcessing,
  testResult,
  testing,
}: {
  canWrite: boolean;
  form: ChannelFormState;
  onFormChange: (form: ChannelFormState) => void;
  onTest: () => void;
  selected: boolean;
  testProcessing: ChannelProcessingResult | null;
  testResult: InboundMessageResponse | null;
  testing: boolean;
}) {
  const { t } = useLocale();
  const [resultTab, setResultTab] = useState<ChannelTestResultTab>("routing");
  const hasResult = Boolean(testResult || testProcessing);

  return (
    <section className="panel channel-test-panel">
      <h2>{t("channelsNormalizeTest")}</h2>
      <label>
        {t("channelsTestText")}
        <input
          disabled={!canWrite}
          value={form.testText}
          onChange={(event) => onFormChange({ ...form, testText: event.target.value })}
        />
      </label>
      <div className="provider-actions">
        <Button onClick={onTest} disabled={!canWrite || !selected || testing}>
          <SendHorizontal size={16} /> {testing ? t("channelsTesting") : t("channelsRunTest")}
        </Button>
      </div>
      {hasResult && (
        <div className="nested-workspace channel-test-result">
          <PageTabs
            active={resultTab}
            onChange={setResultTab}
            tabs={[
              {
                id: "routing",
                label: t("channelsTestResultRouting"),
                description: t("channelsTestResultRoutingDesc"),
              },
              {
                id: "normalized",
                label: t("channelsTestResultNormalized"),
                description: t("channelsTestResultNormalizedDesc"),
              },
              {
                id: "evidence",
                label: t("channelsTestResultEvidence"),
                description: t("channelsTestResultEvidenceDesc"),
              },
            ]}
          />
          {resultTab === "routing" && testProcessing && (
            <section className="channel-test-summary">
              <div className={cx("form-message", testProcessing.error ? "error" : false)}>
                {formatProcessingMessage(testProcessing, t)}
              </div>
              <div className="channel-test-metrics">
                <TestMetric
                  label={t("channelsRoutingState")}
                  value={testProcessing.routed ? t("channelsRoutingRouted") : t("channelsRoutingNotRouted")}
                  status={testProcessing.routed ? "active" : "disabled"}
                />
                <TestMetric label={t("channelsRoutingAgent")} value={testProcessing.agent_key ?? "-"} />
                <TestMetric label={t("channelsRoutingConversation")} value={testProcessing.conversation_id ?? "-"} />
              </div>
            </section>
          )}
          {resultTab === "normalized" && testResult && (
            <pre className="json-preview">
              {JSON.stringify(
                {
                  channel_type: testResult.channel_type,
                  conversation_key: testResult.conversation_key,
                  external_user_id: testResult.external_user_id,
                  message_type: testResult.message_type,
                  received_at: testResult.received_at,
                  signature: testResult.signature,
                  text: testResult.text,
                  trace_id: testResult.trace_id,
                },
                null,
                2,
              )}
            </pre>
          )}
          {resultTab === "evidence" && (
            <div className="channel-test-metrics">
              <TestMetric
                label={t("channelsRoutingExecution")}
                value={evidenceValue(testProcessing, "channel_execution") ?? "-"}
              />
              <TestMetric
                label={t("channelsRoutingRequest")}
                value={
                  evidenceValue(testProcessing, "request_id") ??
                  testProcessing?.request_id ??
                  testResult?.request_id ??
                  "-"
                }
              />
              <TestMetric
                label={t("channelsRoutingProvider")}
                value={evidenceValue(testProcessing, "provider_key") ?? "-"}
              />
              <TestMetric
                label={t("channelsRoutingModel")}
                value={evidenceValue(testProcessing, "model_key") ?? testProcessing?.model_key ?? "-"}
              />
              <TestMetric
                label={t("channelsRoutingGateway")}
                value={gatewayEvidence(testProcessing, t)}
                status={evidenceValue(testProcessing, "llm_gateway_called") === "true" ? "active" : "disabled"}
              />
              <TestMetric label={t("channelsRoutingTrace")} value={testResult?.trace_id ?? "-"} />
              <TestMetric
                label={t("channelsRoutingSignature")}
                value={signatureEvidence(testResult, t)}
                status={testResult?.signature.checked ? (testResult.signature.valid ? "active" : "error") : "disabled"}
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function TestMetric({ label, status, value }: { label: string; status?: string; value: string }) {
  return (
    <article className="channel-test-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {status && <StatusBadge status={status} />}
    </article>
  );
}

function signatureEvidence(testResult: InboundMessageResponse | null, t: (key: string) => string) {
  if (!testResult?.signature.checked) {
    return t("channelsSignatureNotChecked");
  }
  return testResult.signature.valid ? t("channelsSignatureValid") : t("channelsSignatureInvalid");
}

function evidenceValue(testProcessing: ChannelProcessingResult | null, key: string) {
  const value = testProcessing?.runtime_evidence?.[key] ?? testProcessing?.metadata?.[key];
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return String(value);
}

function gatewayEvidence(testProcessing: ChannelProcessingResult | null, t: (key: string) => string) {
  const value = evidenceValue(testProcessing, "llm_gateway_called");
  if (value === "true") {
    return t("channelsGatewayCalled");
  }
  if (value === "false") {
    return t("channelsGatewaySkipped");
  }
  return "-";
}
