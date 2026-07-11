"use client";

import type { AgentStatus, AgentType } from "@/types";
import type { FC, SVGProps } from "react";
import {
  BookIcon,
  LightbulbIcon,
  ShieldCheckIcon,
  ZapIcon,
  ChevronDownIcon,
  RefreshIcon,
} from "./icons";

type IconComponent = FC<SVGProps<SVGSVGElement>>;

interface AgentCardProps {
  agent: AgentType;
  status: AgentStatus;
  primaryModel: string;
  isExpanded?: boolean;
  onToggle?: () => void;
}

const AGENT_META: Record<
  AgentType,
  { name: string; description: string; tone: string; Icon: IconComponent }
> = {
  reader: {
    name: "Reader",
    description: "Parses the question",
    tone: "text-semantic-reader",
    Icon: BookIcon,
  },
  solver: {
    name: "Solver",
    description: "Drafts the solution",
    tone: "text-semantic-solver",
    Icon: LightbulbIcon,
  },
  validator: {
    name: "Validator",
    description: "Checks correctness",
    tone: "text-semantic-validator",
    Icon: ShieldCheckIcon,
  },
  optimizer: {
    name: "Optimizer",
    description: "Finalizes the answer",
    tone: "text-semantic-optimizer",
    Icon: ZapIcon,
  },
};

const statusLabel = (s: AgentStatus["status"]) =>
  s === "running"
    ? "Working"
    : s === "done"
      ? "Complete"
      : s === "error"
        ? "Error"
        : "Idle";

function shortenModel(id: string): string {
  // "meta-llama/llama-3.3-70b-instruct:free" -> "llama-3.3-70b-instruct"
  const slash = id.lastIndexOf("/");
  const base = slash >= 0 ? id.slice(slash + 1) : id;
  return base.replace(/:free$/, "");
}

const fmt = (n: number) => n.toLocaleString();

export const AgentCard: FC<AgentCardProps> = ({
  agent,
  status,
  primaryModel,
  isExpanded = false,
  onToggle,
}) => {
  const { name, description, tone, Icon } = AGENT_META[agent];
  const isActive = status.status === "running";
  const isDone = status.status === "done";
  const isError = status.status === "error";
  const isFallback = !!status.modelUsed && status.modelUsed !== primaryModel;

  return (
    <div
      className={`bg-bg-2 border rounded-xl overflow-hidden transition-colors shadow-soft ${
        isDone
          ? "border-accent-primary/30"
          : isActive
            ? "border-accent-primary/40"
            : isError
              ? "border-semantic-danger/40"
              : "border-border"
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left flex items-center gap-3 p-3 cursor-pointer hover:bg-bg-3/40 transition-colors"
      >
        <span
          className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-bg-3 ${tone}`}
        >
          <Icon width={15} height={15} />
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-text-primary leading-tight">{name}</div>
          <div className="text-xs text-text-muted mt-0.5">{description}</div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[11px] font-mono ${
              isActive
                ? tone
                : isDone
                  ? "text-accent-success"
                  : isError
                    ? "text-semantic-danger"
                    : "text-text-muted"
            }`}
          >
            {statusLabel(status.status)}
          </span>
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              isActive
                ? "bg-accent-primary animate-pulse"
                : isDone
                  ? "bg-accent-success"
                  : isError
                    ? "bg-semantic-danger"
                    : "bg-border-bright"
            }`}
          />
          {status.output && (
            <ChevronDownIcon
              width={14}
              height={14}
              className={`text-text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
            />
          )}
        </div>
      </button>

      {(status.modelUsed || status.tokens) && (
        <div className="px-3 pb-2.5 -mt-1 flex items-center justify-between gap-2 text-[10px]">
          <div className="flex items-center gap-1.5 min-w-0">
            {isFallback && (
              <span
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-amber/15 text-accent-amber font-medium shrink-0"
                title={`Primary "${shortenModel(primaryModel)}" was unavailable — fell back to this model.`}
              >
                <RefreshIcon width={9} height={9} />
                fallback
              </span>
            )}
            {status.modelUsed && (
              <span
                className="font-mono text-text-muted truncate"
                title={status.modelUsed}
              >
                {shortenModel(status.modelUsed)}
              </span>
            )}
          </div>
          {status.tokens && (
            <span
              className="font-mono text-text-muted shrink-0 tabular-nums"
              title={`${fmt(status.tokens.prompt)} prompt + ${fmt(status.tokens.completion)} completion`}
            >
              {fmt(status.tokens.prompt)} in · {fmt(status.tokens.completion)} out
            </span>
          )}
        </div>
      )}

      {isExpanded && status.output && (
        <div className="border-t border-border p-4 max-h-96 overflow-y-auto bg-bg-1/60">
          <pre className="font-mono text-xs leading-relaxed text-text-secondary whitespace-pre-wrap break-words">
            {status.output}
          </pre>
        </div>
      )}
    </div>
  );
};
