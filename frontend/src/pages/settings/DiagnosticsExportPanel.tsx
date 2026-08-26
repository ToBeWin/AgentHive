import { Archive, Download, FileJson, ShieldCheck, Terminal } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, StatusBadge } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { type AuthUser, adminApi } from "../../lib/api";
import { downloadBlobFile, downloadTextFile } from "../../lib/download";
import { canAccess } from "../../lib/permissions";
import { deliveryStatusLabel } from "./settingsUtils";

const SYSTEM_DIAGNOSTICS_PERMISSION = "system:diagnostics";
const SENSITIVE_KEY_PATTERN = /(secret|password|token|api.?key|master.?key|authorization|credential|license_key)/i;
const SENSITIVE_VALUE_PATTERN = /(bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|[a-z][a-z0-9+.-]*:\/\/[^/\s:]+:[^@\s]+@)/i;

export function DiagnosticsExportPanel({
  diagnostics,
  isPrototype,
  user,
}: {
  diagnostics: SystemDiagnostics | null;
  isPrototype: boolean;
  user: AuthUser | null;
}) {
  const { t } = useLocale();
  const [error, setError] = useState<string | null>(null);
  const [exportedAt, setExportedAt] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [bundleExportedAt, setBundleExportedAt] = useState<string | null>(null);
  const [bundleExporting, setBundleExporting] = useState(false);
  const canExport = isPrototype || canAccess(user, [SYSTEM_DIAGNOSTICS_PERMISSION]);
  const delivery = diagnostics?.readiness.delivery ?? null;

  const exportDiagnostics = async () => {
    if (!canExport || (isPrototype && !diagnostics)) {
      return;
    }
    setError(null);
    setExporting(true);
    try {
      const report = isPrototype && diagnostics ? buildPrototypeReport(diagnostics) : await adminApi.getDiagnostics();
      downloadDiagnostics(report, report.generated_at);
      setExportedAt(report.generated_at);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("settingsDiagnosticsExportFailedDetail"));
    } finally {
      setExporting(false);
    }
  };

  const exportSupportBundle = async () => {
    if (!canExport || (isPrototype && !diagnostics)) {
      return;
    }
    setError(null);
    setBundleExporting(true);
    try {
      if (isPrototype && diagnostics) {
        const report = buildPrototypeReport(diagnostics);
        const generatedAt = report.generated_at;
        downloadDiagnostics(report, generatedAt, "agenthive-prototype-support-bundle");
        setBundleExportedAt(generatedAt);
        return;
      }
      const bundle = await adminApi.getSupportBundle();
      const generatedAt = new Date().toISOString();
      downloadBlobFile(
        bundle.blob,
        bundle.filename ?? `agenthive-support-bundle-${generatedAt.replace(/[:.]/g, "-")}.zip`,
      );
      setBundleExportedAt(generatedAt);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("settingsSupportBundleFailedDetail"));
    } finally {
      setBundleExporting(false);
    }
  };

  return (
    <section className="panel settings-export-panel">
      <div className="settings-export-heading">
        <FileJson size={22} />
        <div>
          <h2>{t("settingsDiagnosticsExport")}</h2>
          <p>{t("settingsDiagnosticsExportHelp")}</p>
        </div>
      </div>
      {exportedAt && (
        <ApiNotice
          title={t("settingsDiagnosticsExported")}
          message={t("settingsDiagnosticsExportedDetail").replace("{{time}}", exportedAt)}
        />
      )}
      {bundleExportedAt && (
        <ApiNotice
          title={t("settingsSupportBundleExported")}
          message={t("settingsSupportBundleExportedDetail").replace("{{time}}", bundleExportedAt)}
        />
      )}
      {error && <ApiNotice title={t("settingsDiagnosticsExportFailed")} message={error} />}
      {!canExport && (
        <ApiNotice
          title={t("settingsDiagnosticsPermissionRequired")}
          message={t("settingsDiagnosticsPermissionRequiredDetail")}
        />
      )}
      <Button variant="primary" onClick={() => void exportDiagnostics()} disabled={!canExport || exporting}>
        <Download size={16} /> {exporting ? t("settingsDownloadingDiagnostics") : t("settingsDownloadDiagnostics")}
      </Button>
      {!diagnostics && <p className="muted">{t("settingsDiagnosticsExportUnavailable")}</p>}
      <SupportBundleGuide
        bundleExporting={bundleExporting}
        canExport={canExport}
        delivery={delivery}
        onExport={() => void exportSupportBundle()}
      />
    </section>
  );
}

function SupportBundleGuide({
  bundleExporting,
  canExport,
  delivery,
  onExport,
}: {
  bundleExporting: boolean;
  canExport: boolean;
  delivery: SystemDiagnostics["readiness"]["delivery"] | null | undefined;
  onExport: () => void;
}) {
  const { t } = useLocale();
  const strictCommand =
    'AGENTHIVE_DIAGNOSTICS_TOKEN="<access-token>" scripts/diagnose.sh --strict --output-dir "diagnostics/$(date -u +%Y%m%dT%H%M%SZ)"';
  const offlineCommand = "scripts/diagnose.sh --output-dir diagnostics/current";

  return (
    <div className="settings-support-bundle">
      <div className="settings-support-heading">
        <Archive size={18} />
        <div>
          <h3>{t("settingsSupportBundle")}</h3>
          <p>{t("settingsSupportBundleHelp")}</p>
        </div>
      </div>
      <div className="settings-support-grid">
        <article className="settings-support-card">
          <ShieldCheck size={18} />
          <span>{t("settingsSupportUiExport")}</span>
          <strong>{canExport ? t("settingsSupportUiExportReady") : t("settingsSupportUiExportLocked")}</strong>
          <p>{t("settingsSupportUiExportDetail")}</p>
        </article>
        <article className="settings-support-card">
          <Terminal size={18} />
          <span>{t("settingsSupportCliBundle")}</span>
          <strong>{t("settingsSupportCliBundleReady")}</strong>
          <p>{t("settingsSupportCliBundleDetail")}</p>
        </article>
      </div>
      <div className="settings-support-status">
        <div>
          <span>{t("settingsSupportDeliverySnapshot")}</span>
          <strong>{delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsDeliveryUnavailable")}</strong>
        </div>
        {delivery && <StatusBadge status={delivery.status} label={deliveryStatusLabel(delivery.status, t)} />}
      </div>
      <div className="settings-support-counts">
        <span>
          <strong>{delivery?.blocker_count ?? "-"}</strong>
          {t("settingsDeliveryBlockers")}
        </span>
        <span>
          <strong>{delivery?.warning_count ?? "-"}</strong>
          {t("settingsDeliveryWarnings")}
        </span>
        <span>
          <strong>{delivery?.checks.length ?? "-"}</strong>
          {t("settingsDeliveryChecks")}
        </span>
      </div>
      <Button variant="secondary" onClick={onExport} disabled={!canExport || bundleExporting}>
        <Download size={16} />{" "}
        {bundleExporting ? t("settingsSupportBundleDownloading") : t("settingsDownloadSupportBundle")}
      </Button>
      <CommandBlock label={t("settingsSupportStrictCommand")} command={strictCommand} />
      <CommandBlock label={t("settingsSupportOfflineCommand")} command={offlineCommand} />
    </div>
  );
}

function CommandBlock({ command, label }: { command: string; label: string }) {
  return (
    <div className="settings-command-block">
      <span>{label}</span>
      <pre>
        <code>{command}</code>
      </pre>
    </div>
  );
}

function buildPrototypeReport(diagnostics: SystemDiagnostics) {
  const generatedAt = new Date().toISOString();
  return {
    product: "AgentHive",
    report_type: "deployment_diagnostics",
    generated_at: generatedAt,
    schema_version: "1.0",
    redacted: true,
    delivery: diagnostics.readiness.delivery ?? null,
    diagnostics: redactDiagnostics(diagnostics),
  };
}

function downloadDiagnostics(report: unknown, generatedAt: string, prefix = "agenthive-diagnostics") {
  downloadTextFile(
    JSON.stringify(report, null, 2),
    `${prefix}-${generatedAt.replace(/[:.]/g, "-")}.json`,
    "application/json",
  );
}

function redactDiagnostics(value: unknown, key = ""): unknown {
  if (SENSITIVE_KEY_PATTERN.test(key)) {
    return "[REDACTED]";
  }
  if (typeof value === "string") {
    return SENSITIVE_VALUE_PATTERN.test(value) ? "[REDACTED]" : value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactDiagnostics(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([entryKey, entryValue]) => [
        entryKey,
        redactDiagnostics(entryValue, entryKey),
      ]),
    );
  }
  return value;
}
