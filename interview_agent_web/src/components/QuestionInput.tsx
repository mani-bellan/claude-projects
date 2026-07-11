"use client";

import type { Category } from "@/types";
import type { FC } from "react";
import { CloseIcon } from "./icons";

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  category: Category;
  isRunning: boolean;
  onSubmit: () => void;
  onCancel?: () => void;
}

export const QuestionInput: FC<QuestionInputProps> = ({
  value,
  onChange,
  category,
  isRunning,
  onSubmit,
  onCancel,
}) => {
  const charCount = value.length;
  const maxChars = 2000;

  return (
    <section className="bg-bg-2 border border-border rounded-xl overflow-hidden shadow-soft">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-secondary">Your question</span>
          <span className="text-[11px] px-1.5 py-0.5 rounded font-mono bg-bg-3 text-text-muted2">
            {category}
          </span>
        </div>
      </div>

      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, maxChars))}
        disabled={isRunning}
        placeholder="Ask your data engineering interview question..."
        className="w-full min-h-32 border-none outline-none bg-transparent text-text-primary text-sm leading-relaxed p-4 resize-none disabled:opacity-50"
      />

      <div className="flex items-center justify-between px-4 py-2.5 border-t border-border gap-3">
        <span className="text-xs text-text-muted tabular-nums">
          {charCount} / {maxChars}
        </span>
        <div className="flex items-center gap-2">
          {isRunning && onCancel && (
            <button
              onClick={onCancel}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-border-bright bg-transparent text-text-muted2 transition-colors hover:border-semantic-danger/60 hover:text-semantic-danger"
              aria-label="Cancel running pipeline"
              title="Cancel"
            >
              <CloseIcon width={12} height={12} />
              Cancel
            </button>
          )}
          <button
            onClick={onSubmit}
            disabled={isRunning || !value.trim()}
            className={`text-sm font-medium px-5 py-2 rounded-lg border-none cursor-pointer transition-all flex items-center gap-2 ${
              isRunning || !value.trim()
                ? "bg-accent-primary/30 text-white/60 cursor-not-allowed"
                : "bg-accent-primary text-white hover:bg-accent-hover shadow-soft"
            }`}
          >
            {isRunning ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing
              </>
            ) : (
              "Analyze question"
            )}
          </button>
        </div>
      </div>
    </section>
  );
};
