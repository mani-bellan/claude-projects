"use client";

import { EXAMPLE_QUESTIONS } from "@/lib/constants";
import type { Category, RemoteQuestions } from "@/types";
import type { FC } from "react";
import { useMemo } from "react";
import { RefreshIcon, ExternalLinkIcon } from "./icons";

interface ExamplesListProps {
  category: Category;
  onSelectExample: (question: string) => void;
  remote: RemoteQuestions | null;
  remoteLoading: boolean;
  remoteError: string | null;
  onRefresh: () => void;
}

function relativeTime(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 30_000) return "just now";
  if (diff < 60 * 60_000) return `${Math.round(diff / 60_000)}m ago`;
  if (diff < 24 * 60 * 60_000) return `${Math.round(diff / (60 * 60_000))}h ago`;
  return `${Math.round(diff / (24 * 60 * 60_000))}d ago`;
}

export const ExamplesList: FC<ExamplesListProps> = ({
  category,
  onSelectExample,
  remote,
  remoteLoading,
  remoteError,
  onRefresh,
}) => {
  const merged = useMemo(() => {
    const bundled = EXAMPLE_QUESTIONS[category] ?? [];
    const fetched = remote?.questions[category] ?? [];
    const seen = new Set<string>();
    const result: { text: string; source: "bundled" | "remote" }[] = [];
    for (const t of bundled) {
      const key = t.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      result.push({ text: t, source: "bundled" });
    }
    for (const t of fetched) {
      const key = t.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      result.push({ text: t, source: "remote" });
    }
    return result;
  }, [category, remote]);

  const fetchedCount = remote?.questions[category]?.length ?? 0;

  return (
    <div className="bg-bg-2 border border-border rounded-xl overflow-hidden shadow-soft">
      <div className="px-4 py-2.5 border-b border-border flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-text-secondary">Examples</span>
        <button
          onClick={onRefresh}
          disabled={remoteLoading}
          aria-label="Refresh questions from public source"
          title="Refresh questions from public source"
          className="text-text-muted hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-wait"
        >
          <RefreshIcon
            width={13}
            height={13}
            className={remoteLoading ? "animate-spin" : ""}
          />
        </button>
      </div>
      <div className="p-2 flex flex-col gap-0.5 max-h-72 overflow-y-auto">
        {merged.length === 0 ? (
          <div className="text-xs text-text-muted px-3 py-2">No examples available</div>
        ) : (
          merged.map((item, idx) => (
            <button
              key={`${item.source}-${idx}`}
              onClick={() => onSelectExample(item.text)}
              className="text-left px-2.5 py-2 rounded-md text-xs leading-relaxed text-text-muted2 hover:bg-bg-1 hover:text-text-primary transition-colors border border-transparent hover:border-border flex items-start gap-2"
            >
              <span className="flex-1">{item.text}</span>
              {item.source === "remote" && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-bg-3 text-text-muted shrink-0 mt-0.5">
                  CB
                </span>
              )}
            </button>
          ))
        )}
      </div>
      <div className="px-3 py-2 border-t border-border text-[11px] text-text-muted flex items-center justify-between gap-2">
        {remoteError ? (
          <span className="text-semantic-danger truncate" title={remoteError}>
            Couldn&apos;t load remote
          </span>
        ) : remote ? (
          <>
            <span
              className="truncate"
              title={
                remote.sources
                  ?.map((s) => `${s.label}: ${s.ok ? s.count : s.error ?? "failed"}`)
                  .join("\n") ?? remote.source
              }
            >
              +{fetchedCount} this category · {remote.total} total · {relativeTime(remote.fetchedAt)}
            </span>
            <a
              href={remote.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open source"
              className="text-text-muted hover:text-text-primary shrink-0"
            >
              <ExternalLinkIcon width={11} height={11} />
            </a>
          </>
        ) : remoteLoading ? (
          <span>Loading from public sources…</span>
        ) : (
          <span>Bundled examples only</span>
        )}
      </div>
    </div>
  );
};
