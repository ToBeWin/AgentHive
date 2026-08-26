import { agentModulesZh } from "./agentModules.zh";
import { agentsZh } from "./agents.zh";
import { auditZh } from "./audit.zh";
import { budgetsZh } from "./budgets.zh";
import { builderZh } from "./builder.zh";
import { channelsZh } from "./channels.zh";
import { chatZh } from "./chat.zh";
import { commonZh } from "./common.zh";
import { departmentsZh } from "./departments.zh";
import { knowledgeZh } from "./knowledge.zh";
import { licenseZh } from "./license.zh";
import { mediaZh } from "./media.zh";
import { modelsZh } from "./models.zh";
import { overviewZh } from "./overview.zh";
import { settingsZh } from "./settings.zh";
import type { Messages } from "./types";

export const zhCNMessages: Messages = {
  ...commonZh,
  ...agentsZh,
  ...auditZh,
  ...agentModulesZh,
  ...builderZh,
  ...licenseZh,
  ...mediaZh,
  ...channelsZh,
  ...departmentsZh,
  ...knowledgeZh,
  ...chatZh,
  ...overviewZh,
  ...modelsZh,
  ...budgetsZh,
  ...settingsZh,
};
