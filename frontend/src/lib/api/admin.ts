import { agentsApi } from "./agents";
import { analyticsApi } from "./analytics";
import { auditApi } from "./audit";
import { budgetsApi } from "./budgets";
import { builderApi } from "./builder";
import { channelsApi } from "./channels";
import { chatApi } from "./chat";
import { knowledgeApi } from "./knowledge";
import { agentModulesApi, licenseApi } from "./license";
import { mcpApi } from "./mcp";
import { modelsApi } from "./models";
import { orgApi } from "./org";
import { systemApi } from "./system";

export const adminApi = {
  ...licenseApi,
  ...agentModulesApi,
  ...agentsApi,
  ...builderApi,
  ...mcpApi,
  ...modelsApi,
  ...budgetsApi,
  ...channelsApi,
  ...knowledgeApi,
  ...orgApi,
  ...chatApi,
  ...analyticsApi,
  ...auditApi,
  ...systemApi,
};
