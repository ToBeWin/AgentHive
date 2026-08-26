import { CheckCircle2, RadioTower, SlidersHorizontal, XCircle } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMConnectionTestResponse, LLMDeploymentAcceptanceTestResponse } from "../../lib/api";
import { MediaProviderProbeControls } from "./MediaProviderProbeControls";
import type { CredentialFormState } from "./modelUtils";

interface CredentialDiagnosticsPanelProps {
  canWrite: boolean;
  credentialForm: CredentialFormState;
  isMedia: boolean;
  lastAcceptanceResult: LLMDeploymentAcceptanceTestResponse | null;
  lastTestResult: LLMConnectionTestResponse | null;
  onAcceptanceTest: () => void;
  onLiveProbe: () => void;
  onTestConnection: () => void;
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>;
  testing: boolean;
}

interface RouteAttempt {
  attempt?: number;
  deployment_id?: string;
  error_code?: string;
  error_message?: string;
  latency_ms?: number;
  message?: string;
  model_key?: string;
  provider_key?: string;
  routing_key?: string;
  status?: string;
}

export function CredentialDiagnosticsPanel({
  canWrite,
  credentialForm,
  isMedia,
  lastAcceptanceResult,
  lastTestResult,
  onAcceptanceTest,
  onLiveProbe,
  onTestConnection,
  setCredentialForm,
  testing,
}: CredentialDiagnosticsPanelProps) {
  const { t } = useLocale();

  return (
    <>
      <div className="provider-actions">
        <Button onClick={onTestConnection} disabled={!canWrite || testing}>
          <SlidersHorizontal size={16} /> {testing ? t("modelsTesting") : t("modelsTest")}
        </Button>
        <Button onClick={onAcceptanceTest} disabled={!canWrite || testing}>
          <CheckCircle2 size={16} /> {testing ? t("modelsTesting") : t("modelsRunAcceptanceTest")}
        </Button>
      </div>
      {isMedia && (
        <MediaProviderProbeControls
          credentialForm={credentialForm}
          canWrite={canWrite}
          onLiveProbe={onLiveProbe}
          setCredentialForm={setCredentialForm}
          testing={testing}
        />
      )}
      {!isMedia && (
        <LiveModelProbeControls
          credentialForm={credentialForm}
          canWrite={canWrite}
          onLiveProbe={onLiveProbe}
          setCredentialForm={setCredentialForm}
          testing={testing}
        />
      )}
      {lastTestResult ? (
        <ConnectionDiagnostics result={lastTestResult} />
      ) : (
        <div className="inline-note">{t("modelsNoConnectionDiagnostics")}</div>
      )}
      {lastAcceptanceResult && <AcceptanceDiagnostics result={lastAcceptanceResult} />}
    </>
  );
}

function LiveModelProbeControls({
  canWrite,
  credentialForm,
  onLiveProbe,
  setCredentialForm,
  testing,
}: {
  canWrite: boolean;
  credentialForm: CredentialFormState;
  onLiveProbe: () => void;
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>;
  testing: boolean;
}) {
  const { t } = useLocale();

  return (
    <div className="media-live-probe model-live-probe">
      <div>
        <strong>{t("modelsLiveProbe")}</strong>
        <span>{t("modelsLiveProbeHelp")}</span>
      </div>
      <label>
        {t("modelsProbePath")}
        <input
          disabled={!canWrite}
          placeholder="/models"
          value={credentialForm.probePath}
          onChange={(event) => {
            setCredentialForm((current) => ({ ...current, probePath: event.target.value }));
          }}
        />
      </label>
      <Button onClick={onLiveProbe} disabled={!canWrite || testing}>
        <RadioTower size={16} /> {testing ? t("modelsTesting") : t("modelsRunLiveProbe")}
      </Button>
    </div>
  );
}

function AcceptanceDiagnostics({ result }: { result: LLMDeploymentAcceptanceTestResponse }) {
  const { t } = useLocale();
  const attempts = result.route_attempts;

  return (
    <div className={cx("connection-diagnostics", result.ok ? "ok" : "error")}>
      <div className="connection-diagnostics-header">
        <div>
          <h3>{t("modelsAcceptanceDiagnostics")}</h3>
          <span>
            {result.provider_key} · {result.model_key} · {result.routing_key}
          </span>
        </div>
        <strong>{result.usage.total_tokens} tokens</strong>
      </div>
      <div className="connection-diagnostics-meta">
        <span>{result.request_id}</span>
        {result.live_network_call && <span>{t("modelsLiveNetworkCall")}</span>}
        {result.mock && <span>{t("modelsMockConnection")}</span>}
        {result.usage_recorded && <span>{t("modelsUsageRecorded")}</span>}
      </div>
      <p>{result.ok ? result.content_preview : t("modelsProviderReadinessFailureDetail")}</p>
      {attempts.length > 0 && (
        <div className="connection-attempt-list">
          {attempts.map((attempt, index) => {
            const deploymentId = readAttemptString(attempt, "deployment_id");
            const modelKey = readAttemptString(attempt, "model_key");
            const providerKey = readAttemptString(attempt, "provider_key");
            const routingKey = readAttemptString(attempt, "routing_key");
            const status = readAttemptString(attempt, "status") ?? "unknown";
            const isOk = status === "success";
            return (
              <div className={cx("connection-attempt", isOk ? "ok" : "error")} key={deploymentId ?? index}>
                <span className="connection-attempt-icon">
                  {isOk ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                </span>
                <div>
                  <strong>
                    {providerKey ?? result.provider_key} · {modelKey ?? result.model_key}
                  </strong>
                  <span>{routingKey ?? result.routing_key}</span>
                  <small>{isOk ? t("modelsConnectionHealthy") : t("modelsProviderReadinessFailureDetail")}</small>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function readAttemptString(attempt: Record<string, unknown>, key: string): string | null {
  const value = attempt[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function ConnectionDiagnostics({ result }: { result: LLMConnectionTestResponse }) {
  const { t } = useLocale();
  const attempts = getRouteAttempts(result);
  const fallbackCount = Number(result.diagnostics.fallback_attempt_count ?? 0);
  const operation = typeof result.diagnostics.operation === "string" ? result.diagnostics.operation : "";
  const liveNetworkCall = result.diagnostics.live_network_call === true;
  const statusCode = typeof result.diagnostics.status_code === "number" ? String(result.diagnostics.status_code) : null;

  return (
    <div className={cx("connection-diagnostics", result.ok ? "ok" : "error")}>
      <div className="connection-diagnostics-header">
        <div>
          <h3>{t("modelsConnectionDiagnostics")}</h3>
          <span>
            {result.ok ? t("modelsConnectionHealthy") : t("modelsConnectionFailed")} ·{" "}
            {fallbackCount > 0 ? `${fallbackCount} ${t("modelsFallbacksUsed")}` : t("modelsNoFallbackUsed")}
          </span>
        </div>
        <strong>{result.latency_ms}ms</strong>
      </div>
      {(operation || liveNetworkCall || statusCode) && (
        <div className="connection-diagnostics-meta">
          {operation && <span>{operation}</span>}
          {liveNetworkCall && <span>{t("modelsLiveNetworkCall")}</span>}
          {statusCode && <span>HTTP {statusCode}</span>}
        </div>
      )}
      <p>
        {result.ok
          ? t("modelsConnectionAccepted")
              .replace("{{provider}}", result.provider_key ?? t("modelsUnknownProvider"))
              .replace("{{latency}}", String(result.latency_ms))
          : t("modelsProviderReadinessFailureDetail")}
      </p>
      {attempts.length > 0 && (
        <div className="connection-attempt-list">
          {attempts.map((attempt, index) => {
            const status = attempt.status ?? "unknown";
            const isOk = status === "success";
            return (
              <div className={cx("connection-attempt", isOk ? "ok" : "error")} key={attempt.deployment_id ?? index}>
                <span className="connection-attempt-icon">
                  {isOk ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                </span>
                <div>
                  <strong>
                    {attempt.provider_key ?? t("modelsUnknownProvider")} · {attempt.model_key ?? result.model_key}
                  </strong>
                  <span>
                    {attempt.routing_key ?? t("modelsNotSet")} ·{" "}
                    {attempt.latency_ms !== undefined
                      ? `${attempt.latency_ms}ms`
                      : isOk
                        ? t("modelsConnectionHealthy")
                        : t("modelsConnectionFailed")}
                  </span>
                  <small>{isOk ? t("modelsConnectionHealthy") : t("modelsProviderReadinessFailureDetail")}</small>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function getRouteAttempts(result: LLMConnectionTestResponse): RouteAttempt[] {
  const value = result.diagnostics.route_attempts;
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is RouteAttempt => Boolean(item) && typeof item === "object");
}
