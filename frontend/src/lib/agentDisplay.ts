import type { Locale } from "../i18n";

type AgentDisplaySource = {
  agent_key: string;
  description?: string | null;
  name: string;
};

const AGENT_DISPLAY: Record<
  string,
  {
    en: { description: string; name: string };
    zh: { description: string; name: string };
  }
> = {
  content_analysis: {
    en: {
      description: "Analyze viral content hooks, structure, rhythm, and reusable patterns.",
      name: "Viral Content Analysis Agent",
    },
    zh: {
      description: "拆解爆款内容的钩子、结构、节奏和可复用套路。",
      name: "爆款内容拆解助手",
    },
  },
  copywriting: {
    en: {
      description: "Generate channel-specific product copy and campaign drafts.",
      name: "Copywriting Agent",
    },
    zh: {
      description: "生成小红书、抖音、朋友圈和店铺等多渠道文案。",
      name: "文案创作助手",
    },
  },
  customer_service: {
    en: {
      description: "Handle customer questions with SOP retrieval, policy evidence, and escalation guidance.",
      name: "E-commerce Customer Service Agent",
    },
    zh: {
      description: "基于售后 SOP、政策依据和升级规则处理客户问题。",
      name: "电商客服助手",
    },
  },
  data_analyst: {
    en: {
      description: "Answer business metric questions and explain trends.",
      name: "Data Analyst Agent",
    },
    zh: {
      description: "回答经营指标问题、解释趋势并生成分析结论。",
      name: "数据分析助手",
    },
  },
  finance: {
    en: {
      description: "Explain finance policies, reports, and common accounting workflows.",
      name: "Finance Efficiency Agent",
    },
    zh: {
      description: "解读财务制度、报表和常见财务流程。",
      name: "财务效率助手",
    },
  },
  hr_screening: {
    en: {
      description: "Screen resumes, score job fit, and prepare interview follow-ups.",
      name: "HR Resume Screening Agent",
    },
    zh: {
      description: "解析简历、评估岗位匹配度并生成面试追问。",
      name: "人事简历筛选助手",
    },
  },
  image_generation: {
    en: {
      description: "Create product image prompts, variants, and reference-image edit plans.",
      name: "Product Image Generation Agent",
    },
    zh: {
      description: "生成商品图提示词、多图变体和参考图重绘方案。",
      name: "商品图片生成助手",
    },
  },
  product_design: {
    en: {
      description: "Create product ideas, selling point briefs, and launch material directions.",
      name: "New Product Design Agent",
    },
    zh: {
      description: "生成新品创意、卖点提炼和上市物料方向。",
      name: "新品设计辅助",
    },
  },
  report_writer: {
    en: {
      description: "Turn project facts into weekly reports, monthly reports, and executive summaries.",
      name: "Project Report Agent",
    },
    zh: {
      description: "把项目事实整理成周报、月报和管理层摘要。",
      name: "项目汇报助手",
    },
  },
  store_operations: {
    en: {
      description: "Optimize listings, promotion plans, and store operation suggestions.",
      name: "Store Operations Agent",
    },
    zh: {
      description: "优化商品标题、详情、活动方案和店铺运营建议。",
      name: "店铺运营助手",
    },
  },
  video_generation: {
    en: {
      description: "Plan short videos from prompts, reference assets, and raw material.",
      name: "Short Video Generation Agent",
    },
    zh: {
      description: "基于提示词、参考素材和原始视频规划短视频生成任务。",
      name: "短视频生成助手",
    },
  },
};

export function agentDisplayName(agent: AgentDisplaySource, locale: Locale) {
  return AGENT_DISPLAY[agent.agent_key]?.[localeKey(locale)].name ?? agent.name;
}

export function agentDisplayDescription(agent: AgentDisplaySource, locale: Locale) {
  return AGENT_DISPLAY[agent.agent_key]?.[localeKey(locale)].description ?? agent.description;
}

export function localizedTaskTitle(title: string, locale: Locale) {
  if (locale !== "zh-CN") {
    return title;
  }
  if (/^readiness smoke\b/i.test(title)) {
    return "就绪验证";
  }
  if (/^codex smoke test clean answer\b/i.test(title)) {
    return "回复清洗验证";
  }
  if (/^codex smoke test final\b/i.test(title)) {
    return "最终联调验证";
  }
  if (/^codex smoke test\b/i.test(title)) {
    return "联调验证";
  }
  if (/^Smoke check\b/i.test(title)) {
    return title.replace(/^Smoke check/i, "验收测试");
  }
  if (/E-commerce Customer Service Agent/i.test(title)) {
    return title.replace(/E-commerce Customer Service Agent/gi, AGENT_DISPLAY.customer_service.zh.name);
  }
  if (/HR Resume Screening Agent/i.test(title)) {
    return title.replace(/HR Resume Screening Agent/gi, AGENT_DISPLAY.hr_screening.zh.name);
  }
  return title;
}

function localeKey(locale: Locale) {
  return locale === "zh-CN" ? "zh" : "en";
}

/**
 * Pick a max_tokens budget based on the agent type so long-form agents
 * (reports, analysis) aren't truncated and short-form agents (chat) stay lean.
 * Backend caps at 8192; these values are well within that envelope.
 */
export function maxTokensForAgent(agentKey: string | undefined | null): number {
  if (!agentKey) return 1024;
  // Long-form generators: reports, data analysis, finance
  if (["report_writer", "data_analyst", "finance"].includes(agentKey)) return 4096;
  // Creative / structured copy: marketing, design, content
  if (["copywriting", "product_design", "content_analysis"].includes(agentKey)) return 2048;
  // Conversational agents: customer service, HR, store ops
  return 1024;
}
