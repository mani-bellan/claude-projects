"use client";

import type { FC } from "react";
import { LogoIcon, SettingsIcon, CheckIcon } from "./icons";

interface HeaderProps {
  onSettingsClick: () => void;
  isApiKeySet: boolean;
}

const STEPS = [
  { id: "reader", label: "Reader" },
  { id: "solver", label: "Solver" },
  { id: "validator", label: "Validator" },
  { id: "optimizer", label: "Optimizer" },
];

export const Header: FC<HeaderProps> = ({ onSettingsClick, isApiKeySet }) => {
  return (
    <header className="mb-8">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-primary to-accent-blue/80 text-white flex items-center justify-center shadow-soft">
            <LogoIcon width={18} height={18} strokeWidth={2} />
          </div>
          <div>
            <h1 className="font-display text-lg font-semibold text-text-primary tracking-tightish leading-none">
              DE Interview Helper
            </h1>
            <p className="text-xs text-text-muted mt-1.5">
              Multi-agent assistant · OpenRouter · BYOK
            </p>
          </div>
        </div>
        <button
          onClick={onSettingsClick}
          className={`inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border transition-colors whitespace-nowrap ${
            isApiKeySet
              ? "border-accent-primary/30 bg-accent-subtle text-accent-hover hover:border-accent-primary/60"
              : "border-border-bright bg-bg-2 text-text-muted2 hover:border-accent-primary/60 hover:text-text-primary"
          }`}
        >
          {isApiKeySet ? <CheckIcon width={14} height={14} /> : <SettingsIcon width={14} height={14} />}
          {isApiKeySet ? "API key set" : "Set API key"}
        </button>
      </div>

      <div className="flex items-center bg-bg-2 border border-border rounded-xl overflow-hidden">
        {STEPS.map((step, idx) => (
          <div
            key={step.id}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 text-xs text-text-muted2 ${
              idx < STEPS.length - 1 ? "border-r border-border" : ""
            }`}
          >
            <span className="font-mono text-[10px] text-text-muted tabular-nums">
              {String(idx + 1).padStart(2, "0")}
            </span>
            <span>{step.label}</span>
          </div>
        ))}
      </div>
    </header>
  );
};
