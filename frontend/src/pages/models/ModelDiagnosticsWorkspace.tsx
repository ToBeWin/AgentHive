import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestHistoryItem,
  LLMDeploymentResponse,
  LLMPolicyResponse,
  LLMProviderResponse,
  LLMReadinessResponse,
} from "../../lib/api";
import { ModelConnectionHistoryPanel } from "./ModelConnectionHistoryPanel";
import { ModelHandoffChecklistPanel } from "./ModelHandoffChecklistPanel";
import type { ModelDiagnosticsTab } from "./modelWorkspaceTypes";

interface ModelDiagnosticsWorkspaceProps {
  connectionHistory: LLMConnectionTestHistoryItem[];
  diagnosticsTab: ModelDiagnosticsTab;
  deploymentsList: LLMDeploymentResponse[];
  historyError: string | null;
  historyLoading: boolean;
  modelReadiness: LLMReadinessResponse | null | undefined;
  onDiagnosticsTabChange: (tab: ModelDiagnosticsTab) => void;
  onOpenCoverage: () => void;
  onOpenCredentials: () => void;
  onOpenDiagnostics: () => void;
  onOpenGovernance: () => void;
  policiesList: LLMPolicyResponse[];
  pricesCount: number;
  providersList: LLMProviderResponse[];
  refetchHistory: () => void;
}

export function ModelDiagnosticsWorkspace({
  connectionHistory,
  deploymentsList,
  diagnosticsTab,
  historyError,
  historyLoading,
  modelReadiness,
  onDiagnosticsTabChange,
  onOpenCoverage,
  onOpenCredentials,
  onOpenDiagnostics,
  onOpenGovernance,
  policiesList,
  pricesCount,
  providersList,
  refetchHistory,
}: ModelDiagnosticsWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace model-diagnostics-workspace">
      <PageTabs
        active={diagnosticsTab}
        onChange={onDiagnosticsTabChange}
        tabs={[
          {
            id: "handoff",
            label: t("modelsDiagnosticsTabHandoff"),
            description: t("modelsDiagnosticsTabHandoffDesc"),
          },
          {
            id: "history",
            label: t("modelsDiagnosticsTabHistory"),
            description: t("modelsDiagnosticsTabHistoryDesc"),
          },
        ]}
      />
      {diagnosticsTab === "handoff" && (
        <ModelHandoffChecklistPanel
          connectionHistory={connectionHistory}
          deployments={deploymentsList}
          modelReadiness={modelReadiness}
          onOpenCoverage={onOpenCoverage}
          onOpenCredentials={onOpenCredentials}
          onOpenDiagnostics={onOpenDiagnostics}
          onOpenGovernance={onOpenGovernance}
          policies={policiesList}
          pricesCount={pricesCount}
          providers={providersList}
        />
      )}
      {diagnosticsTab === "history" && (
        <ModelConnectionHistoryPanel
          historyError={historyError}
          historyList={connectionHistory}
          historyLoading={historyLoading}
          refetchHistory={refetchHistory}
        />
      )}
    </div>
  );
}
