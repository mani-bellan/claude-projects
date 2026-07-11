"use client";

import { useCallback, useRef, useState } from "react";
import { useInterviewStore } from "@/store";
import { fetchSwarmStream } from "@/lib/api";
import type { AgentType, Category } from "@/types";

const ALL_AGENTS: AgentType[] = ["reader", "solver", "validator", "optimizer"];

export function useSwarmStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const runSwarm = useCallback(
    async (question: string, category: Category, apiKey: string) => {
      const store = useInterviewStore.getState();

      if (!apiKey) {
        store.setError("API key is required. Please set it in the settings.");
        return;
      }

      // Replace any in-flight controller; cancel() can target this one.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setIsStreaming(true);
      store.startPipeline();
      store.resetAgents();
      const startTime = Date.now();

      const completed = new Set<AgentType>();
      let hadError = false;

      try {
        for await (const event of fetchSwarmStream(
          question,
          category,
          apiKey,
          store.agentModels,
          controller.signal
        )) {
          if (event.type === "start") {
            useInterviewStore.getState().setAgentStatus(event.agent, "running");
          } else if (event.type === "model") {
            useInterviewStore.getState().setAgentMeta(event.agent, {
              modelUsed: event.model,
              tokens: event.usage,
            });
          } else if (event.type === "chunk") {
            const current = useInterviewStore.getState();
            current.setAgentOutput(
              event.agent,
              current.agents[event.agent].output + (event.content ?? "")
            );
          } else if (event.type === "end") {
            const elapsed = Date.now() - startTime;
            const current = useInterviewStore.getState();
            current.setAgentStatus(event.agent, "done");
            current.setAgentElapsed(event.agent, elapsed);
            if (event.usage) {
              current.setAgentMeta(event.agent, { tokens: event.usage });
            }
            completed.add(event.agent);
          } else if (event.type === "error") {
            hadError = true;
            const current = useInterviewStore.getState();
            current.setAgentStatus(event.agent, "error");
            current.setError(`${event.agent}: ${event.error ?? "unknown error"}`);
          }
        }

        // Only persist to history if the full pipeline finished cleanly. Partial
        // runs (errors or cancellation) would otherwise pollute history with
        // half-empty solutions that the "load from history" flow can't render.
        const allDone = ALL_AGENTS.every((a) => completed.has(a));
        if (allDone && !hadError && !controller.signal.aborted) {
          const final = useInterviewStore.getState();
          final.addToHistory({
            id: `${Date.now()}`,
            question,
            category,
            timestamp: Date.now(),
            results: {
              reader: final.agents.reader.output,
              solver: final.agents.solver.output,
              validator: final.agents.validator.output,
              optimizer: final.agents.optimizer.output,
            },
          });
        }
        useInterviewStore.getState().endPipeline();
      } catch (error) {
        // AbortError is an expected outcome of cancel() — not a user-facing error.
        const isAbort =
          (error instanceof DOMException && error.name === "AbortError") ||
          (error instanceof Error && error.name === "AbortError");
        const current = useInterviewStore.getState();
        if (!isAbort) {
          const message = error instanceof Error ? error.message : "Unknown error";
          current.setError(message);
        }
        current.endPipeline();
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setIsStreaming(false);
      }
    },
    []
  );

  return { runSwarm, cancel, isStreaming };
}
