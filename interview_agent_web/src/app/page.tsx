"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Header,
  ApiKeyModal,
  ErrorBanner,
  CategorySelector,
  ExamplesList,
  QuestionInput,
  AgentCard,
  ResultsPanel,
  UsageBar,
} from "@/components";
import { useInterviewStore } from "@/store";
import { useSwarmStream } from "@/hooks/useSwarmStream";
import { useApiKeyModal } from "@/hooks/useApiKeyModal";
import { saveAsMarkdown } from "@/lib/utils";

export default function Home() {
  const question = useInterviewStore((s) => s.question);
  const category = useInterviewStore((s) => s.category);
  const isRunning = useInterviewStore((s) => s.isRunning);
  const error = useInterviewStore((s) => s.error);
  const agents = useInterviewStore((s) => s.agents);
  const setQuestion = useInterviewStore((s) => s.setQuestion);
  const setCategory = useInterviewStore((s) => s.setCategory);
  const setError = useInterviewStore((s) => s.setError);
  const agentModels = useInterviewStore((s) => s.agentModels);
  const setAgentModels = useInterviewStore((s) => s.setAgentModels);
  const remote = useInterviewStore((s) => s.remote);
  const remoteLoading = useInterviewStore((s) => s.remoteLoading);
  const remoteError = useInterviewStore((s) => s.remoteError);
  const setRemote = useInterviewStore((s) => s.setRemote);
  const setRemoteLoading = useInterviewStore((s) => s.setRemoteLoading);
  const setRemoteError = useInterviewStore((s) => s.setRemoteError);

  const { runSwarm, cancel } = useSwarmStream();
  const modal = useApiKeyModal();
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const refreshRemote = useCallback(async () => {
    setRemoteLoading(true);
    setRemoteError(null);
    try {
      const res = await fetch("/api/questions", { cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setRemote(data);
    } catch (err) {
      setRemoteError(err instanceof Error ? err.message : "Failed to load");
    }
  }, [setRemote, setRemoteLoading, setRemoteError]);

  useEffect(() => {
    // useApiKeyModal owns the key. It auto-loads from localStorage on mount;
    // if nothing was found by the time we run, prompt the user.
    if (!modal.apiKey) {
      modal.open();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Auto-fetch remote questions on first visit; the server-side cache
    // (revalidate: 3600) prevents hammering GitHub.
    if (!remote && !remoteLoading && !remoteError) {
      refreshRemote();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRun = async () => {
    const apiKey = modal.apiKey;
    if (!apiKey) {
      setError("API key is required. Please set it in the settings.");
      modal.open();
      return;
    }
    await runSwarm(question, category, apiKey);
  };

  const handleSaveMarkdown = () => {
    saveAsMarkdown({
      question,
      category,
      results: {
        reader: agents.reader.output,
        solver: agents.solver.output,
        validator: agents.validator.output,
        optimizer: agents.optimizer.output,
      },
      timestamp: Date.now(),
    });
  };

  const handleModalSave = (key: string, models: typeof agentModels) => {
    modal.save(key);
    setAgentModels(models);
  };

  return (
    <div className="min-h-screen bg-bg-0 text-text-primary">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 0%, rgba(99,102,241,0.10), transparent 45%), radial-gradient(circle at 100% 100%, rgba(56,189,248,0.06), transparent 50%)",
        }}
      />
      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 pb-16">
        <Header onSettingsClick={() => modal.open()} isApiKeySet={!!modal.apiKey} />
        <ErrorBanner error={error} onDismiss={() => setError(null)} />

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6 lg:gap-8 items-start">
          <div className="flex flex-col gap-6 order-2 lg:order-1">
            <CategorySelector selected={category} onChange={setCategory} />
            <ExamplesList
              category={category}
              onSelectExample={setQuestion}
              remote={remote}
              remoteLoading={remoteLoading}
              remoteError={remoteError}
              onRefresh={refreshRemote}
            />
          </div>

          <div className="flex flex-col gap-6 order-1 lg:order-2">
            <QuestionInput
              value={question}
              onChange={setQuestion}
              category={category}
              isRunning={isRunning}
              onSubmit={handleRun}
              onCancel={cancel}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {(["reader", "solver", "validator", "optimizer"] as const).map((agent) => (
                <AgentCard
                  key={agent}
                  agent={agent}
                  status={agents[agent]}
                  primaryModel={agentModels[agent]}
                  isExpanded={expandedAgent === agent}
                  onToggle={() =>
                    setExpandedAgent(expandedAgent === agent ? null : agent)
                  }
                />
              ))}
            </div>

            <UsageBar agents={agents} />

            <ResultsPanel
              isVisible={agents.optimizer.status === "done"}
              category={category}
              optimizerOutput={agents.optimizer.output}
              onSaveMarkdown={handleSaveMarkdown}
            />
          </div>
        </div>
      </div>

      <ApiKeyModal
        isOpen={modal.isOpen}
        onClose={modal.close}
        onSave={handleModalSave}
        initialKey={modal.apiKey}
        initialModels={agentModels}
      />
    </div>
  );
}
