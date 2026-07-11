"use client";

import type { AgentStatus, AgentType } from "@/types";
import type { FC } from "react";

interface UsageBarProps {
  agents: Record<AgentType, AgentStatus>;
}

const AGENT_LABEL: Record<AgentType, string> = {
  reader: "Reader",
  solver: "Solver",
  validator: "Validator",
  optimizer: "Optimizer",
};

const fmt = (n: number) => n.toLocaleString();

export const UsageBar: FC<UsageBarProps> = ({ agents }) => {
  const order: AgentType[] = ["reader", "solver", "validator", "optimizer"];
  const tokensByAgent = order.map((id) => ({ id, tokens: agents[id].tokens }));
  const anyTokens = tokensByAgent.some((t) => !!t.tokens);
  if (!anyTokens) return null;

  const totals = tokensByAgent.reduce(
    (acc, { tokens }) => {
      if (!tokens) return acc;
      acc.prompt += tokens.prompt;
      acc.completion += tokens.completion;
      acc.total += tokens.total;
      return acc;
    },
    { prompt: 0, completion: 0, total: 0 }
  );

  return (
    <div className="bg-bg-2 border border-border rounded-xl px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap shadow-soft">
      <div className="flex items-center gap-3 flex-wrap text-[11px] font-mono text-text-muted tabular-nums">
        {tokensByAgent.map(({ id, tokens }) => (
          <span key={id} className="flex items-center gap-1.5">
            <span className="text-text-muted2">{AGENT_LABEL[id]}</span>
            <span className={tokens ? "text-text-secondary" : "text-text-muted/50"}>
              {tokens ? fmt(tokens.total) : "—"}
            </span>
          </span>
        ))}
      </div>
      <div
        className="flex items-center gap-3 text-[11px] font-mono tabular-nums"
        title="Sum across all agents that have completed so far"
      >
        <span className="text-text-muted">
          <span className="text-text-secondary">{fmt(totals.prompt)}</span> in
        </span>
        <span className="text-border-bright">·</span>
        <span className="text-text-muted">
          <span className="text-text-secondary">{fmt(totals.completion)}</span> out
        </span>
        <span className="text-border-bright">·</span>
        <span className="text-text-primary font-medium">{fmt(totals.total)} total</span>
      </div>
    </div>
  );
};
