import { agentModulesEn } from "./agentModules";
import { agentsEn } from "./agents";
import { auditEn } from "./audit";
import { budgetsEn } from "./budgets";
import { builderEn } from "./builder";
import { channelsEn } from "./channels";
import { chatEn } from "./chat";
import { commonEn } from "./common";
import { departmentsEn } from "./departments";
import { knowledgeEn } from "./knowledge";
import { licenseEn } from "./license";
import { mediaEn } from "./media";
import { modelsEn } from "./models";
import { overviewEn } from "./overview";
import { settingsEn } from "./settings";
import type { Messages } from "./types";

export const enUSMessages: Messages = {
  ...commonEn,
  ...agentsEn,
  ...auditEn,
  ...agentModulesEn,
  ...builderEn,
  ...licenseEn,
  ...mediaEn,
  ...channelsEn,
  ...departmentsEn,
  ...knowledgeEn,
  ...chatEn,
  ...overviewEn,
  ...modelsEn,
  ...budgetsEn,
  ...settingsEn,
};
