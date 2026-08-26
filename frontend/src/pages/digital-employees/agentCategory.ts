import type { WorkbenchAgentInstanceResponse } from "../../lib/api";

export type EmployeeCategory =
  | "all"
  | "customer"
  | "marketing"
  | "hr"
  | "media"
  | "operations"
  | "finance"
  | "analytics"
  | "general";

export const categoryOrder: EmployeeCategory[] = [
  "all",
  "customer",
  "marketing",
  "hr",
  "media",
  "operations",
  "finance",
  "analytics",
  "general",
];

const promptStarterKeys = [
  "digitalEmployeesPromptCustomerReply",
  "digitalEmployeesPromptActionList",
  "digitalEmployeesPromptProductCopy",
] as const;

interface AgentWorkbenchProfile {
  actions: readonly string[];
  category: Exclude<EmployeeCategory, "all">;
  inputs: readonly string[];
  outputs: readonly string[];
  steps: readonly string[];
}

const PROFILE_BY_AGENT_KEY: Record<string, AgentWorkbenchProfile> = {
  content_analysis: {
    actions: ["agentWorkflowContentBreakdown", "agentWorkflowSellingPoints", "agentWorkflowChannelVariants"],
    category: "marketing",
    inputs: ["agentInputContentLink", "agentInputTargetAudience", "agentInputChannel"],
    outputs: ["agentOutputContentAngles", "agentOutputSellingPoints", "agentOutputChecklist"],
    steps: ["agentStepReadBrief", "agentStepExtractSellingPoints", "agentStepGenerateVariants", "agentStepPolishTone"],
  },
  copywriting: {
    actions: ["agentWorkflowProductCopy", "agentWorkflowChannelVariants", "agentWorkflowSellingPoints"],
    category: "marketing",
    inputs: ["agentInputProductInfo", "agentInputChannel", "agentInputTone"],
    outputs: ["agentOutputCopy", "agentOutputVariants", "agentOutputChecklist"],
    steps: ["agentStepReadBrief", "agentStepExtractSellingPoints", "agentStepGenerateVariants", "agentStepPolishTone"],
  },
  customer_service: {
    actions: ["agentWorkflowCustomerReply", "agentWorkflowSopLookup", "agentWorkflowEscalation"],
    category: "customer",
    inputs: ["agentInputCustomerQuestion", "agentInputOrderContext", "agentInputPolicyScope"],
    outputs: ["agentOutputReply", "agentOutputEvidence", "agentOutputFollowUp"],
    steps: ["agentStepUnderstandIssue", "agentStepRetrievePolicy", "agentStepDraftAnswer", "agentStepEscalateIfNeeded"],
  },
  data_analyst: {
    actions: ["agentWorkflowMetricExplain", "agentWorkflowTrendInsight", "agentWorkflowDataQuestion"],
    category: "analytics",
    inputs: ["agentInputBusinessData", "agentInputMetricQuestion", "agentInputTimeRange"],
    outputs: ["agentOutputInsight", "agentOutputChartPlan", "agentOutputRecommendation"],
    steps: ["agentStepReadData", "agentStepAnalyzeSignal", "agentStepGenerateResult", "agentStepSuggestNext"],
  },
  finance: {
    actions: ["agentWorkflowFinanceExplain", "agentWorkflowExpenseCheck", "agentWorkflowReportInsight"],
    category: "finance",
    inputs: ["agentInputFinancePolicy", "agentInputStatement", "agentInputAccountingQuestion"],
    outputs: ["agentOutputFinanceAnswer", "agentOutputRiskNote", "agentOutputReconciliationSteps"],
    steps: ["agentStepCheckRules", "agentStepReadData", "agentStepAnalyzeSignal", "agentStepPrepareRecommendation"],
  },
  hr_screening: {
    actions: ["agentWorkflowResumeSummary", "agentWorkflowInterviewQuestions", "agentWorkflowFitScore"],
    category: "hr",
    inputs: ["agentInputResume", "agentInputJobDescription", "agentInputHiringCriteria"],
    outputs: ["agentOutputSummary", "agentOutputScore", "agentOutputQuestions"],
    steps: ["agentStepParseResume", "agentStepMatchRole", "agentStepScoreCandidate", "agentStepPrepareInterview"],
  },
  image_generation: {
    actions: ["agentWorkflowImagePrompt", "agentWorkflowReferenceRedraw", "agentWorkflowAssetChecklist"],
    category: "media",
    inputs: ["agentInputPrompt", "agentInputReferenceAssets", "agentInputMediaSpecs"],
    outputs: ["agentOutputPrompt", "agentOutputImageVariants", "agentOutputAssetPlan"],
    steps: ["agentStepCollectAssets", "agentStepPlanCreative", "agentStepGenerateMedia", "agentStepReviewOutputs"],
  },
  product_design: {
    actions: ["agentWorkflowProductConcept", "agentWorkflowSellingPoints", "agentWorkflowChannelVariants"],
    category: "marketing",
    inputs: ["agentInputProductInfo", "agentInputTargetAudience", "agentInputExpectedFormat"],
    outputs: ["agentOutputProductConcept", "agentOutputSellingPoints", "agentOutputNextSteps"],
    steps: ["agentStepReadBrief", "agentStepExtractSellingPoints", "agentStepGenerateVariants", "agentStepSuggestNext"],
  },
  report_writer: {
    actions: ["agentWorkflowReportDraft", "agentWorkflowActionSummary", "agentWorkflowNextPlan"],
    category: "analytics",
    inputs: ["agentInputBusinessData", "agentInputKnownContext", "agentInputExpectedFormat"],
    outputs: ["agentOutputReport", "agentOutputActionItems", "agentOutputNextSteps"],
    steps: ["agentStepUnderstandTask", "agentStepReadData", "agentStepGenerateResult", "agentStepPolishTone"],
  },
  store_operations: {
    actions: ["agentWorkflowStoreListing", "agentWorkflowPromotionPlan", "agentWorkflowCustomerInsight"],
    category: "operations",
    inputs: ["agentInputStoreGoal", "agentInputShopData", "agentInputProductListing"],
    outputs: ["agentOutputOperationPlan", "agentOutputListingFixes", "agentOutputPromotionChecklist"],
    steps: ["agentStepReadData", "agentStepAnalyzeSignal", "agentStepPrepareRecommendation", "agentStepSuggestNext"],
  },
  video_generation: {
    actions: ["agentWorkflowVideoStoryboard", "agentWorkflowVideoCommand", "agentWorkflowAssetChecklist"],
    category: "media",
    inputs: ["agentInputPrompt", "agentInputReferenceAssets", "agentInputMediaSpecs"],
    outputs: ["agentOutputStoryboard", "agentOutputVideoPlan", "agentOutputAssetPlan"],
    steps: ["agentStepCollectAssets", "agentStepPlanCreative", "agentStepGenerateMedia", "agentStepReviewOutputs"],
  },
};

export function categoryForEmployee(employee: WorkbenchAgentInstanceResponse): EmployeeCategory {
  const explicitCategory = normalizedCategory(employee.category);
  if (explicitCategory) {
    return explicitCategory;
  }
  const profile = profileForEmployee(employee);
  if (profile) {
    return profile.category;
  }
  const key = `${employee.agent_key} ${employee.module_key} ${employee.name}`.toLowerCase();
  if (key.includes("customer") || key.includes("客服") || key.includes("support")) {
    return "customer";
  }
  if (key.includes("copy") || key.includes("content") || key.includes("marketing") || key.includes("文案")) {
    return "marketing";
  }
  if (key.includes("hr") || key.includes("resume") || key.includes("招聘") || key.includes("简历")) {
    return "hr";
  }
  if (key.includes("image") || key.includes("video") || key.includes("media") || key.includes("生成")) {
    return "media";
  }
  if (key.includes("store") || key.includes("shop") || key.includes("运营") || key.includes("店铺")) {
    return "operations";
  }
  if (key.includes("finance") || key.includes("财务") || key.includes("expense") || key.includes("invoice")) {
    return "finance";
  }
  if (key.includes("data") || key.includes("analytics") || key.includes("分析")) {
    return "analytics";
  }
  return "general";
}

export function categoryLabelKey(category: EmployeeCategory) {
  return {
    all: "digitalEmployeesCategoryAll",
    customer: "digitalEmployeesCategoryCustomer",
    general: "digitalEmployeesCategoryGeneral",
    hr: "digitalEmployeesCategoryHr",
    marketing: "digitalEmployeesCategoryMarketing",
    media: "digitalEmployeesCategoryMedia",
    operations: "digitalEmployeesCategoryOperations",
    finance: "digitalEmployeesCategoryFinance",
    analytics: "digitalEmployeesCategoryAnalytics",
  }[category];
}

export function workflowActionKeys(employee: WorkbenchAgentInstanceResponse | null) {
  if (!employee) {
    return promptStarterKeys;
  }
  const profile = profileForEmployee(employee);
  if (profile) {
    return profile.actions;
  }
  const category = categoryForEmployee(employee);
  if (category === "customer") {
    return ["agentWorkflowCustomerReply", "agentWorkflowSopLookup", "agentWorkflowEscalation"] as const;
  }
  if (category === "marketing") {
    return ["agentWorkflowProductCopy", "agentWorkflowChannelVariants", "agentWorkflowSellingPoints"] as const;
  }
  if (category === "hr") {
    return ["agentWorkflowResumeSummary", "agentWorkflowInterviewQuestions", "agentWorkflowFitScore"] as const;
  }
  if (category === "media") {
    return ["agentWorkflowImagePrompt", "agentWorkflowVideoStoryboard", "agentWorkflowAssetChecklist"] as const;
  }
  return promptStarterKeys;
}

export function workflowStepKeys(employee: WorkbenchAgentInstanceResponse | null) {
  const profile = employee ? profileForEmployee(employee) : null;
  if (profile) {
    return profile.steps;
  }
  const category = employee ? categoryForEmployee(employee) : "general";
  if (category === "customer") {
    return ["agentStepUnderstandIssue", "agentStepRetrievePolicy", "agentStepDraftAnswer", "agentStepEscalateIfNeeded"];
  }
  if (category === "marketing") {
    return ["agentStepReadBrief", "agentStepExtractSellingPoints", "agentStepGenerateVariants", "agentStepPolishTone"];
  }
  if (category === "hr") {
    return ["agentStepParseResume", "agentStepMatchRole", "agentStepScoreCandidate", "agentStepPrepareInterview"];
  }
  if (category === "media") {
    return ["agentStepCollectAssets", "agentStepPlanCreative", "agentStepGenerateMedia", "agentStepReviewOutputs"];
  }
  return ["agentStepUnderstandTask", "agentStepUseContext", "agentStepGenerateResult", "agentStepSuggestNext"];
}

export function workflowInputKeys(employee: WorkbenchAgentInstanceResponse | null) {
  const profile = employee ? profileForEmployee(employee) : null;
  if (profile) {
    return profile.inputs;
  }
  const category = employee ? categoryForEmployee(employee) : "general";
  if (category === "customer") {
    return ["agentInputCustomerQuestion", "agentInputOrderContext", "agentInputPolicyScope"];
  }
  if (category === "marketing") {
    return ["agentInputProductInfo", "agentInputChannel", "agentInputTone"];
  }
  if (category === "hr") {
    return ["agentInputResume", "agentInputJobDescription", "agentInputHiringCriteria"];
  }
  if (category === "media") {
    return ["agentInputPrompt", "agentInputReferenceAssets", "agentInputMediaSpecs"];
  }
  return ["agentInputTaskGoal", "agentInputKnownContext", "agentInputExpectedFormat"];
}

export function workflowOutputKeys(employee: WorkbenchAgentInstanceResponse | null) {
  const profile = employee ? profileForEmployee(employee) : null;
  if (profile) {
    return profile.outputs;
  }
  const category = employee ? categoryForEmployee(employee) : "general";
  if (category === "customer") {
    return ["agentOutputReply", "agentOutputEvidence", "agentOutputFollowUp"];
  }
  if (category === "marketing") {
    return ["agentOutputCopy", "agentOutputVariants", "agentOutputChecklist"];
  }
  if (category === "hr") {
    return ["agentOutputSummary", "agentOutputScore", "agentOutputQuestions"];
  }
  if (category === "media") {
    return ["agentOutputPrompt", "agentOutputStoryboard", "agentOutputAssetPlan"];
  }
  return ["agentOutputAnswer", "agentOutputActionItems", "agentOutputNextSteps"];
}

function profileForEmployee(employee: WorkbenchAgentInstanceResponse) {
  return (
    PROFILE_BY_AGENT_KEY[normalizedAgentKey(employee.workflow_profile)] ??
    PROFILE_BY_AGENT_KEY[normalizedAgentKey(employee.agent_key)] ??
    PROFILE_BY_AGENT_KEY[normalizedAgentKey(employee.module_key)]
  );
}

function normalizedAgentKey(value: string | undefined) {
  return (value ?? "").replace(/^agent\./, "").toLowerCase();
}

function normalizedCategory(value: string | undefined): EmployeeCategory | null {
  if (
    value === "customer" ||
    value === "marketing" ||
    value === "hr" ||
    value === "media" ||
    value === "operations" ||
    value === "finance" ||
    value === "analytics" ||
    value === "general"
  ) {
    return value;
  }
  return null;
}
