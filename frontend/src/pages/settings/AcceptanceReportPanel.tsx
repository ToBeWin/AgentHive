import { ClipboardCheck, Download, FileCheck2 } from "lucide-react";
import { Button } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { downloadTextFile } from "../../lib/download";
import { AcceptanceSummaryPanel } from "./AcceptanceSummaryPanel";
import { buildAcceptanceReport } from "./acceptanceReportBuilder";

export function AcceptanceReportPanel({ diagnostics }: { diagnostics: SystemDiagnostics | null }) {
  const { locale, t } = useLocale();
  const generatedAt = new Date().toISOString();
  const disabled = !diagnostics;

  const exportReport = () => {
    if (!diagnostics) {
      return;
    }
    const report = buildAcceptanceReport({
      diagnostics,
      generatedAt,
      locale,
      t,
    });
    downloadTextFile(
      report,
      `agenthive-acceptance-report-${generatedAt.replace(/[:.]/g, "-")}.md`,
      "text/markdown;charset=utf-8",
    );
  };

  return (
    <section className="panel settings-acceptance-panel">
      <div className="settings-export-heading">
        <FileCheck2 size={22} />
        <div>
          <h2>{t("settingsAcceptanceReport")}</h2>
          <p>{t("settingsAcceptanceReportHelp")}</p>
        </div>
      </div>
      <AcceptanceSummaryPanel diagnostics={diagnostics} />
      <div className="settings-acceptance-actions">
        <ClipboardCheck size={18} />
        <p>{t("settingsAcceptanceReportDetail")}</p>
      </div>
      <Button variant="primary" onClick={exportReport} disabled={disabled}>
        <Download size={16} /> {t("settingsDownloadAcceptanceReport")}
      </Button>
      {disabled && <p className="muted">{t("settingsAcceptanceUnavailable")}</p>}
    </section>
  );
}
