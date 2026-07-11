"use client";

import { extractSection } from "@/lib/utils";
import { getMode } from "@/lib/constants";
import type { Category } from "@/types";
import type { FC } from "react";
import { useMemo, useState } from "react";
import { ClockIcon, DatabaseIcon, SparkleIcon, DownloadIcon } from "./icons";

interface ResultsPanelProps {
  isVisible: boolean;
  category: Category;
  optimizerOutput: string;
  onSaveMarkdown: () => void;
}

type CodeTab = "final" | "complexity" | "tips";
type ConceptTab = "final" | "tradeoffs" | "tips";

const CODE_TABS: { id: CodeTab; label: string }[] = [
  { id: "final", label: "Final solution" },
  { id: "complexity", label: "Complexity" },
  { id: "tips", label: "Interview tips" },
];

const CONCEPT_TABS: { id: ConceptTab; label: string }[] = [
  { id: "final", label: "Final answer" },
  { id: "tradeoffs", label: "Trade-offs" },
  { id: "tips", label: "Interview tips" },
];

export const ResultsPanel: FC<ResultsPanelProps> = ({
  isVisible,
  category,
  optimizerOutput,
  onSaveMarkdown,
}) => {
  const mode = getMode(category);
  const [activeTab, setActiveTab] = useState<string>("final");

  const sections = useMemo(() => {
    if (mode === "code") {
      return {
        final: extractSection(optimizerOutput, "FINAL SOLUTION"),
        time: extractSection(optimizerOutput, "TIME COMPLEXITY"),
        space: extractSection(optimizerOutput, "SPACE COMPLEXITY"),
        tips: extractSection(optimizerOutput, "INTERVIEW TIPS"),
      };
    }
    return {
      final: extractSection(optimizerOutput, "FINAL ANSWER"),
      tradeoffs: extractSection(optimizerOutput, "KEY TRADE-OFFS"),
      alternatives: extractSection(optimizerOutput, "ALTERNATIVES CONSIDERED"),
      tips: extractSection(optimizerOutput, "INTERVIEW TIPS"),
    };
  }, [optimizerOutput, mode]);

  if (!isVisible || !optimizerOutput) return null;

  const tabs = mode === "code" ? CODE_TABS : CONCEPT_TABS;

  return (
    <section className="bg-bg-2 border border-border rounded-xl overflow-hidden shadow-soft">
      <div className="flex border-b border-border overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-shrink-0 px-4 py-3 text-xs font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "text-text-primary border-b-accent-primary"
                : "text-text-muted border-b-transparent hover:text-text-secondary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="p-5">
        {activeTab === "final" && (
          <pre className="font-mono text-xs leading-relaxed text-text-secondary whitespace-pre-wrap break-words max-h-[500px] overflow-y-auto">
            {sections.final || "No answer available."}
          </pre>
        )}

        {mode === "code" && activeTab === "complexity" && (
          <div className="grid sm:grid-cols-2 gap-4">
            <InfoCard
              icon={<ClockIcon width={14} height={14} />}
              label="Time complexity"
              body={("time" in sections && sections.time) || "Not provided."}
            />
            <InfoCard
              icon={<DatabaseIcon width={14} height={14} />}
              label="Space complexity"
              body={("space" in sections && sections.space) || "Not provided."}
            />
          </div>
        )}

        {mode === "concept" && activeTab === "tradeoffs" && (
          <div className="flex flex-col gap-4">
            <InfoCard
              icon={<SparkleIcon width={14} height={14} />}
              label="Key trade-offs"
              body={("tradeoffs" in sections && sections.tradeoffs) || "Not provided."}
            />
            <InfoCard
              icon={<SparkleIcon width={14} height={14} />}
              label="Alternatives considered"
              body={("alternatives" in sections && sections.alternatives) || "Not provided."}
            />
          </div>
        )}

        {activeTab === "tips" && (
          <InfoCard
            icon={<SparkleIcon width={14} height={14} />}
            label="Interview tips"
            body={sections.tips || "No tips available."}
          />
        )}
      </div>

      <div className="flex items-center justify-between px-5 py-3 border-t border-border">
        <span className="text-xs text-text-muted">Results ready</span>
        <button
          onClick={onSaveMarkdown}
          className="inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border border-border-bright bg-transparent text-text-muted2 transition-colors hover:border-accent-primary/60 hover:text-text-primary"
        >
          <DownloadIcon width={14} height={14} />
          Save markdown
        </button>
      </div>
    </section>
  );
};

const InfoCard: FC<{ icon: React.ReactNode; label: string; body: string }> = ({
  icon,
  label,
  body,
}) => (
  <div className="bg-bg-1 border border-border rounded-lg p-4">
    <div className="flex items-center gap-2 text-xs font-medium text-text-secondary mb-2">
      <span className="text-accent-primary">{icon}</span>
      {label}
    </div>
    <pre className="font-mono text-xs leading-relaxed text-text-muted2 whitespace-pre-wrap break-words">
      {body}
    </pre>
  </div>
);
