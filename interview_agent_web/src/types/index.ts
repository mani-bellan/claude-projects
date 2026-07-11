export type Category = "coding" | "architecture" | "design" | "sql" | "streaming" | "general";

export type AgentType = "reader" | "solver" | "validator" | "optimizer";

export interface TokenUsage {
  prompt: number;
  completion: number;
  total: number;
}

export interface AgentStatus {
  name: string;
  status: "idle" | "running" | "done" | "error";
  output: string;
  elapsed: number;
  modelUsed?: string;
  tokens?: TokenUsage;
}

export interface RemoteSourceStatus {
  id: string;
  label: string;
  htmlUrl: string;
  ok: boolean;
  count: number;
  error?: string;
}

export interface RemoteQuestions {
  source: string;
  sourceUrl: string;
  fetchedAt: number;
  total: number;
  questions: Partial<Record<Category, string[]>>;
  sources?: RemoteSourceStatus[];
}

export type AgentModels = Record<AgentType, string>;

export interface PipelineState {
  question: string;
  category: Category;
  isRunning: boolean;
  error: string | null;
  agents: Record<AgentType, AgentStatus>;
  history: HistoryItem[];
  remote: RemoteQuestions | null;
  remoteLoading: boolean;
  remoteError: string | null;
  agentModels: AgentModels;
}

export interface HistoryItem {
  id: string;
  question: string;
  category: Category;
  timestamp: number;
  results: Record<AgentType, string>;
}

export interface SwarmResponse {
  reader: string;
  solver: string;
  validator: string;
  optimizer: string;
}

export interface StreamEvent {
  agent: AgentType;
  type: "start" | "chunk" | "end" | "error" | "model";
  content?: string;
  error?: string;
  model?: string;
  usage?: TokenUsage;
}
