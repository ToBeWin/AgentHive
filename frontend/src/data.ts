import type { LucideIcon } from "lucide-react";
import {
  BadgeCheck,
  BarChart3,
  Bot,
  Brain,
  Building2,
  ChartNoAxesCombined,
  CircleDollarSign,
  Database,
  FileText,
  Gauge,
  Headset,
  History,
  KeyRound,
  Landmark,
  Layers3,
  Megaphone,
  MessageSquare,
  Network,
  NotebookText,
  Puzzle,
  ReceiptText,
  Scale,
  Settings,
  Sparkles,
  Users,
  WandSparkles,
} from "lucide-react";

export type PageId =
  | "digitalEmployees"
  | "overview"
  | "agents"
  | "agentModules"
  | "builder"
  | "knowledgeBases"
  | "mediaGeneration"
  | "chatConsole"
  | "channels"
  | "models"
  | "budgets"
  | "departments"
  | "users"
  | "auditLogs"
  | "license"
  | "settings";

export type WorkspaceId = "user" | "admin";

export interface NavItem {
  id: PageId;
  icon: LucideIcon;
  requiredAllPermission?: string[];
  requiredAnyPermission?: string[];
  workspaceRequiredAllPermission?: Partial<Record<WorkspaceId, string[]>>;
  workspaceRequiredAnyPermission?: Partial<Record<WorkspaceId, string[]>>;
  workspaces: WorkspaceId[];
}

export const navItems: NavItem[] = [
  {
    id: "digitalEmployees",
    icon: Bot,
    requiredAnyPermission: ["agents:read", "chat:read", "chat:write"],
    workspaces: ["user"],
  },
  {
    id: "chatConsole",
    icon: MessageSquare,
    requiredAnyPermission: ["audit:read", "system:diagnostics"],
    workspaceRequiredAllPermission: {
      admin: ["audit:read"],
    },
    workspaceRequiredAnyPermission: {
      admin: ["agents:write"],
    },
    workspaces: ["admin"],
  },
  {
    id: "mediaGeneration",
    icon: WandSparkles,
    requiredAnyPermission: ["agents:read", "chat:write", "agents:write"],
    workspaceRequiredAllPermission: {
      user: ["agents:read", "chat:write"],
    },
    workspaceRequiredAnyPermission: {
      admin: ["agents:write"],
    },
    workspaces: ["user", "admin"],
  },
  {
    id: "knowledgeBases",
    icon: Database,
    requiredAnyPermission: ["knowledge:read", "knowledge:write"],
    workspaceRequiredAnyPermission: {
      user: ["knowledge:read", "knowledge:write"],
      admin: ["knowledge:write"],
    },
    workspaces: ["user", "admin"],
  },
  {
    id: "overview",
    icon: BarChart3,
    requiredAnyPermission: ["analytics:read"],
    workspaceRequiredAnyPermission: {
      admin: ["analytics:read"],
    },
    workspaces: ["admin"],
  },
  { id: "agents", icon: Bot, requiredAnyPermission: ["agents:write"], workspaces: ["admin"] },
  {
    id: "agentModules",
    icon: Puzzle,
    requiredAnyPermission: ["agents:write"],
    workspaces: ["admin"],
  },
  {
    id: "channels",
    icon: Network,
    requiredAnyPermission: ["channels:read", "channels:write"],
    workspaces: ["admin"],
  },
  {
    id: "models",
    icon: Gauge,
    requiredAnyPermission: ["models:read", "models:write"],
    workspaceRequiredAnyPermission: {
      admin: ["models:write"],
    },
    workspaces: ["admin"],
  },
  {
    id: "budgets",
    icon: CircleDollarSign,
    requiredAnyPermission: ["budgets:read", "budgets:write"],
    workspaces: ["admin"],
  },
  {
    id: "auditLogs",
    icon: History,
    requiredAnyPermission: ["audit:read"],
    workspaces: ["admin"],
  },
  {
    id: "users",
    icon: Users,
    requiredAnyPermission: ["users:read"],
    workspaces: ["admin"],
  },
  {
    id: "departments",
    icon: Building2,
    requiredAllPermission: ["users:read", "departments:read"],
    workspaceRequiredAnyPermission: {
      admin: ["users:write", "departments:write"],
    },
    workspaces: ["admin"],
  },
  { id: "license", icon: BadgeCheck, requiredAnyPermission: ["license:read", "license:write"], workspaces: ["admin"] },
  { id: "settings", icon: Settings, requiredAnyPermission: ["system:diagnostics"], workspaces: ["admin"] },
];

export const kpis = [
  {
    label: "TOTAL CONVERSATIONS",
    zh: "总对话",
    value: "1.24M",
    delta: "+12.5% vs last month",
    tone: "good",
    icon: MessageSquare,
  },
  { label: "ACTIVE AGENTS", zh: "活跃智能体", value: "48", delta: "Out of 65 deployed", tone: "neutral", icon: Bot },
  {
    label: "MONTHLY MODEL COST",
    zh: "月度模型成本",
    value: "$14,250",
    delta: "+4.2% over budget",
    tone: "bad",
    icon: ReceiptText,
  },
  {
    label: "TOKEN USAGE (B)",
    zh: "Token使用量",
    value: "3.8",
    delta: "-2.1% optimization gain",
    tone: "good",
    icon: ChartNoAxesCombined,
  },
];

export const deptCosts = [
  { name: "Customer Support", cost: "$6,420", pct: 86 },
  { name: "Engineering (R&D)", cost: "$4,150", pct: 61 },
  { name: "Sales Operations", cost: "$2,100", pct: 35 },
  { name: "Marketing Data", cost: "$1,580", pct: 20 },
];

export const modelPerformance = [
  { model: "GPT-4-Turbo", provider: "OA", latency: "845ms", error: "0.02%", rpm: "1,420", status: "HEALTHY" },
  { model: "Claude-3-Opus", provider: "AN", latency: "1,120ms", error: "0.05%", rpm: "850", status: "HEALTHY" },
  { model: "Azure-GPT-3.5", provider: "MS", latency: "420ms", error: "1.20%", rpm: "3,100", status: "DEGRADED" },
];

export const moduleCards = [
  {
    name: "Customer Service Assistant",
    category: "Customer Support",
    status: "INSTALLED",
    description: "Handles tier 1 support queries, ticket routing, and automated reply drafts.",
    icon: Headset,
    licensed: true,
  },
  {
    name: "HR Resume Screening",
    category: "Human Resources",
    status: "ENABLED",
    description: "Parses resumes, scores candidates, and explains match reasons.",
    icon: NotebookText,
    licensed: true,
  },
  {
    name: "Copywriting Assistant",
    category: "Marketing",
    status: "NOT LICENSED",
    description: "Generates campaigns, social posts, and product copy variants.",
    icon: Megaphone,
    licensed: false,
  },
  {
    name: "Content Analysis Assistant",
    category: "Marketing",
    status: "AVAILABLE",
    description: "Analyzes reviews, posts, and content patterns for actionable signals.",
    icon: BarChart3,
    licensed: true,
  },
  {
    name: "Report Writer",
    category: "Operations",
    status: "ENABLED",
    description: "Synthesizes meeting notes and raw data into structured reports.",
    icon: FileText,
    licensed: true,
  },
  {
    name: "Finance Assistant",
    category: "Finance",
    status: "NOT LICENSED",
    description: "Automates invoice processing, expense categorization, and finance Q&A.",
    icon: Landmark,
    licensed: false,
  },
];

export const agents = [
  {
    name: "Customer Support Tier 1",
    key: "cust-support-v2",
    module: "Resolution Bot",
    department: "Customer Success",
    model: "GPT-4o",
    status: "ACTIVE",
    cost: "$1,020",
  },
  {
    name: "Lead Gen Qualifier",
    key: "score-inbound",
    module: "Inbound Sales",
    department: "Sales",
    model: "Claude 3.5",
    status: "DRAFT",
    cost: "$240",
  },
  {
    name: "HR Policy Assistant",
    key: "internal-hr",
    module: "Internal Q&A",
    department: "Human Resources",
    model: "Qwen Plus",
    status: "ACTIVE",
    cost: "$390",
  },
  {
    name: "Refund Policy Bot",
    key: "refund-helper",
    module: "Support",
    department: "Customer Success",
    model: "DeepSeek",
    status: "DISABLED",
    cost: "$85",
  },
];

export const providers = [
  { name: "OpenAI", status: "CONNECTED", detail: "sk-proj-...8f9a", icon: Sparkles },
  { name: "Anthropic", status: "CONNECTED", detail: "sk-ant-...22b1", icon: Brain },
  { name: "Google Vertex", status: "CONNECTED", detail: "Service Account", icon: KeyRound },
  { name: "DeepSeek", status: "ERROR", detail: "Auth Failed", icon: Scale },
  { name: "Ollama", status: "LOCAL", detail: "http://localhost:11434", icon: Layers3 },
];

export const deployments = [
  { model: "gpt-4o", provider: "OpenAI | LLM", caps: "stream tools vision", status: "ACTIVE", latency: "420ms" },
  {
    model: "claude-3-5-sonnet",
    provider: "Anthropic | LLM",
    caps: "stream tools vision",
    status: "ACTIVE",
    latency: "380ms",
  },
  {
    model: "gemini-1.5-pro",
    provider: "Google | LLM",
    caps: "stream tools vision",
    status: "ACTIVE",
    latency: "510ms",
  },
  {
    model: "text-embedding-3-large",
    provider: "OpenAI | Embedding",
    caps: "embedding",
    status: "ACTIVE",
    latency: "85ms",
  },
  { model: "llama3-8b", provider: "Ollama | LLM", caps: "local", status: "STANDBY", latency: "120ms" },
];

export const budgetRows = [
  { name: "Engineering", limit: "$20,000.00", spent: "$12,400.00", usage: "62.0%", status: "NORMAL" },
  { name: "Customer Success", limit: "$10,000.00", spent: "$8,500.00", usage: "85.0%", status: "WARNING" },
  { name: "Marketing", limit: "$5,000.00", spent: "$2,250.00", usage: "45.0%", status: "NORMAL" },
  { name: "Sales", limit: "$8,000.00", spent: "$1,200.00", usage: "15.0%", status: "NORMAL" },
];

export const knowledgeBases = [
  { name: "HR Policies 2024", docs: "142 Docs", size: "1.2 GB", selected: true },
  { name: "Technical Specs Q3", docs: "89 Docs", size: "450 MB" },
  { name: "Customer Support Logs", docs: "1,204 Docs", size: "5.4 GB" },
];

export const documents = [
  { file: "employee_handbook_v2.pdf", type: "PDF", status: "READY" },
  { file: "pto_guidelines_2024.docx", type: "DOCX", status: "READY" },
  { file: "q1_benefits_faq.csv", type: "CSV", status: "READY" },
  { file: "corrupted_scan.pdf", type: "PDF", status: "ERROR" },
];

export const users = [
  {
    name: "Alice Lee",
    role: "OrgAdmin",
    department: "Operations",
    costCenter: "OPS-001",
    login: "Today 09:21",
    status: "ACTIVE",
  },
  {
    name: "John Doe",
    role: "AgentManager",
    department: "Engineering",
    costCenter: "ENG-042",
    login: "Today 08:44",
    status: "ACTIVE",
  },
  {
    name: "Mei Chen",
    role: "KBManager",
    department: "Customer Success",
    costCenter: "CS-118",
    login: "Yesterday",
    status: "ACTIVE",
  },
  {
    name: "Owen Park",
    role: "ReadOnly",
    department: "Finance",
    costCenter: "FIN-009",
    login: "3 days ago",
    status: "DISABLED",
  },
];

export const auditRows = [
  {
    time: "2026-06-08 14:32:01",
    actor: "John Doe (Eng)",
    action: "Create Agent",
    resource: "agent_customer_support_v2",
    status: "SUCCESS",
    ip: "192.168.1.104",
  },
  {
    time: "2026-06-08 14:15:22",
    actor: "System (Auto-Scale)",
    action: "Deploy Model",
    resource: "model_gpt4_turbo_prod",
    status: "SUCCESS",
    ip: "10.0.0.5",
  },
  {
    time: "2026-06-08 13:58:45",
    actor: "Alice Lee (Ops)",
    action: "Delete KB",
    resource: "kb_legacy_docs_2021",
    status: "FAILURE",
    ip: "192.168.1.205",
  },
  {
    time: "2026-06-08 13:45:10",
    actor: "John Doe (Eng)",
    action: "Login",
    resource: "N/A",
    status: "SUCCESS",
    ip: "192.168.1.104",
  },
  {
    time: "2026-06-08 12:30:00",
    actor: "System (Sync Job)",
    action: "Update Budget",
    resource: "dept_engineering_q4",
    status: "SUCCESS",
    ip: "10.0.0.12",
  },
];

export const chatMessages = [
  { role: "assistant", text: "Customer Support Tier 1 is online. Ask a product, refund, or logistics question." },
  { role: "user", text: "A customer wants a refund after 18 days. What should we say?" },
  {
    role: "assistant",
    text: "The refund window is 15 days for standard items. I found two policy chunks. Suggest apologizing, checking exception eligibility, and offering store credit if the item is unopened.",
  },
];
