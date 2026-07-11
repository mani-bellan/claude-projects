import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  PipelineState,
  HistoryItem,
  AgentType,
  AgentModels,
  Category,
  AgentStatus,
  RemoteQuestions,
  TokenUsage,
} from "@/types";
import { DEFAULT_AGENT_MODELS } from "@/lib/models";

interface InterviewStore extends PipelineState {
  // Per-agent model selection
  setAgentModel: (agent: AgentType, modelId: string) => void;
  setAgentModels: (models: AgentModels) => void;
  resetAgentModels: () => void;

  // Question and category
  setQuestion: (question: string) => void;
  setCategory: (category: Category) => void;

  // Pipeline execution
  startPipeline: () => void;
  endPipeline: () => void;
  setError: (error: string | null) => void;

  // Agent updates
  setAgentStatus: (agent: AgentType, status: AgentStatus["status"]) => void;
  setAgentOutput: (agent: AgentType, output: string) => void;
  setAgentElapsed: (agent: AgentType, elapsed: number) => void;
  setAgentMeta: (agent: AgentType, meta: { modelUsed?: string; tokens?: TokenUsage }) => void;
  resetAgents: () => void;

  // History
  addToHistory: (item: HistoryItem) => void;
  clearHistory: () => void;
  loadFromHistory: (id: string) => void;

  // Remote questions
  setRemote: (remote: RemoteQuestions) => void;
  setRemoteLoading: (loading: boolean) => void;
  setRemoteError: (error: string | null) => void;
}

const initialAgentStatus: AgentStatus = {
  name: "",
  status: "idle",
  output: "",
  elapsed: 0,
};

export const useInterviewStore = create<InterviewStore>()(
  persist(
    (set, get) => ({
      // Initial state
      question: "",
      category: "general",
      isRunning: false,
      error: null,
      agents: {
        reader: { ...initialAgentStatus, name: "Question Reader" },
        solver: { ...initialAgentStatus, name: "Solution Producer" },
        validator: { ...initialAgentStatus, name: "Validator" },
        optimizer: { ...initialAgentStatus, name: "Optimizer" },
      },
      history: [],
      remote: null,
      remoteLoading: false,
      remoteError: null,
      agentModels: { ...DEFAULT_AGENT_MODELS },

      // Per-agent model selection
      setAgentModel: (agent, modelId) =>
        set((state) => ({
          agentModels: { ...state.agentModels, [agent]: modelId },
        })),
      setAgentModels: (models) => set({ agentModels: { ...models } }),
      resetAgentModels: () => set({ agentModels: { ...DEFAULT_AGENT_MODELS } }),

      // Question and category
      setQuestion: (question: string) => set({ question }),
      setCategory: (category: Category) => set({ category }),

      // Pipeline execution
      startPipeline: () => set({ isRunning: true, error: null }),
      endPipeline: () => set({ isRunning: false }),
      setError: (error: string | null) => set({ error }),

      // Agent updates
      setAgentStatus: (agent: AgentType, status: AgentStatus["status"]) =>
        set((state) => ({
          agents: {
            ...state.agents,
            [agent]: { ...state.agents[agent], status },
          },
        })),

      setAgentOutput: (agent: AgentType, output: string) =>
        set((state) => ({
          agents: {
            ...state.agents,
            [agent]: { ...state.agents[agent], output },
          },
        })),

      setAgentElapsed: (agent: AgentType, elapsed: number) =>
        set((state) => ({
          agents: {
            ...state.agents,
            [agent]: { ...state.agents[agent], elapsed },
          },
        })),

      setAgentMeta: (agent: AgentType, meta: { modelUsed?: string; tokens?: TokenUsage }) =>
        set((state) => ({
          agents: {
            ...state.agents,
            [agent]: { ...state.agents[agent], ...meta },
          },
        })),

      resetAgents: () =>
        set({
          agents: {
            reader: { ...initialAgentStatus, name: "Question Reader" },
            solver: { ...initialAgentStatus, name: "Solution Producer" },
            validator: { ...initialAgentStatus, name: "Validator" },
            optimizer: { ...initialAgentStatus, name: "Optimizer" },
          },
        }),

      // History
      addToHistory: (item: HistoryItem) =>
        set((state) => ({
          history: [item, ...state.history].slice(0, 20), // Keep last 20
        })),

      clearHistory: () => set({ history: [] }),

      // Remote questions
      setRemote: (remote: RemoteQuestions) =>
        set({ remote, remoteLoading: false, remoteError: null }),
      setRemoteLoading: (loading: boolean) => set({ remoteLoading: loading }),
      setRemoteError: (remoteError: string | null) =>
        set({ remoteError, remoteLoading: false }),

      loadFromHistory: (id: string) => {
        const state = get();
        const item = state.history.find((h) => h.id === id);
        if (item) {
          set({
            question: item.question,
            category: item.category,
            agents: {
              reader: { ...state.agents.reader, output: item.results.reader },
              solver: { ...state.agents.solver, output: item.results.solver },
              validator: { ...state.agents.validator, output: item.results.validator },
              optimizer: { ...state.agents.optimizer, output: item.results.optimizer },
            },
          });
        }
      },
    }),
    {
      name: "interview-store",
      version: 1,
      partialize: (state) => ({
        history: state.history,
        category: state.category,
        agentModels: state.agentModels,
      }),
    }
  )
);
