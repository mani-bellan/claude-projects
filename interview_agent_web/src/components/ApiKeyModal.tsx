"use client";

import { useEffect, useMemo, useState } from "react";
import type { FC } from "react";
import type { AgentModels, AgentType } from "@/types";
import {
  MODEL_CATALOG,
  DEFAULT_AGENT_MODELS,
  type ModelOption,
} from "@/lib/models";
import { CloseIcon, RefreshIcon } from "./icons";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (key: string, models: AgentModels) => void;
  initialKey: string;
  initialModels: AgentModels;
}

const AGENT_LABELS: Record<AgentType, string> = {
  reader: "Reader",
  solver: "Solver",
  validator: "Validator",
  optimizer: "Optimizer",
};

const AGENT_HINT: Record<AgentType, string> = {
  reader: "Classifies the question. Small model is fine.",
  solver: "Drafts the solution. Use your strongest model.",
  validator: "Reviews the draft. Mid-size is usually enough.",
  optimizer: "Produces the final answer. Use your strongest model.",
};

const CUSTOM_VALUE = "__custom__";

export const ApiKeyModal: FC<ApiKeyModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialKey,
  initialModels,
}) => {
  const [key, setKey] = useState(initialKey);
  const [models, setModels] = useState<AgentModels>(initialModels);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ModelOption[] | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    setKey(initialKey);
    setModels(initialModels);
    setError(null);
  }, [initialKey, initialModels, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    if (catalog) return; // already loaded this session
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError(null);
    fetch("/api/models")
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<{ models: ModelOption[] }>;
      })
      .then((data) => {
        if (cancelled) return;
        if (Array.isArray(data.models) && data.models.length > 0) {
          setCatalog(data.models);
        } else {
          setCatalog(MODEL_CATALOG);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setCatalog(MODEL_CATALOG);
        setCatalogError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, catalog]);

  const effectiveCatalog = catalog ?? MODEL_CATALOG;
  const lookup = useMemo(
    () => new Map(effectiveCatalog.map((m) => [m.id, m])),
    [effectiveCatalog]
  );

  if (!isOpen) return null;

  const handleSave = () => {
    const trimmed = key.trim();
    if (!trimmed) {
      setError("API key is required.");
      return;
    }
    if (!/^sk-or-[\w-]{20,}$/.test(trimmed)) {
      setError("OpenRouter keys start with 'sk-or-' and are at least 24 characters.");
      return;
    }
    onSave(trimmed, models);
  };

  const resetModels = () => setModels({ ...DEFAULT_AGENT_MODELS });

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div
        className="bg-bg-2 border border-border-bright rounded-2xl p-6 max-w-xl w-full shadow-soft max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 id="settings-title" className="text-lg font-semibold text-text-primary tracking-tightish">
              Settings
            </h2>
            <p className="text-xs text-text-muted2 leading-relaxed mt-1">
              Bring your own OpenRouter key and pick a model per agent. Stored only in your browser.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-bg-3 transition-colors"
          >
            <CloseIcon width={14} height={14} />
          </button>
        </div>

        <section className="mb-6">
          <label
            htmlFor="api-key-input"
            className="block text-xs font-medium text-text-secondary mb-1.5"
          >
            OpenRouter API key
          </label>
          <input
            id="api-key-input"
            type="password"
            value={key}
            onChange={(e) => {
              setKey(e.target.value);
              if (error) setError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
            }}
            placeholder="sk-or-v1-..."
            spellCheck={false}
            autoComplete="off"
            className="w-full bg-bg-1 border border-border-bright rounded-lg px-3 py-2.5 font-mono text-sm text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-accent-primary"
          />
          <p className="text-[11px] text-text-muted mt-1.5">
            Get one at{" "}
            <a
              href="https://openrouter.ai/keys"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-hover hover:underline"
            >
              openrouter.ai/keys
            </a>
            . Free-tier models cost $0 (look for the &quot;:free&quot; suffix).
          </p>
        </section>

        <section className="mb-6">
          <div className="flex items-center justify-between mb-2 gap-2">
            <h3 className="text-xs font-medium text-text-secondary">Models per agent</h3>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setCatalog(null); // triggers refetch via the catalog effect
                }}
                disabled={catalogLoading}
                aria-label="Refresh model list from OpenRouter"
                title="Refresh model list from OpenRouter"
                className="text-text-muted hover:text-text-primary transition-colors disabled:opacity-50 disabled:cursor-wait"
              >
                <RefreshIcon
                  width={12}
                  height={12}
                  className={catalogLoading ? "animate-spin" : ""}
                />
              </button>
              <button
                type="button"
                onClick={resetModels}
                className="text-[11px] text-text-muted hover:text-text-primary transition-colors"
              >
                Reset to defaults
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-3">
            {(Object.keys(AGENT_LABELS) as AgentType[]).map((agent) => (
              <ModelRow
                key={agent}
                agent={agent}
                value={models[agent]}
                catalog={effectiveCatalog}
                lookup={lookup}
                onChange={(modelId) => setModels((m) => ({ ...m, [agent]: modelId }))}
              />
            ))}
          </div>
          <p className="text-[11px] text-text-muted mt-2 leading-relaxed">
            {catalogLoading
              ? "Loading live model list from OpenRouter…"
              : catalogError
                ? `Couldn't fetch the live model list (${catalogError}). Showing a curated fallback — pick "Custom model id…" to enter any model.`
                : `Free models (“:free”) require enabling "Free model publication" at openrouter.ai/settings/privacy. If a free model 404s, that's why.`}
          </p>
        </section>

        {error && (
          <p className="text-xs text-semantic-danger mb-3" role="alert">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleSave}
            className="flex-1 text-sm font-medium py-2.5 rounded-lg bg-accent-primary text-white transition-colors hover:bg-accent-hover"
          >
            Save
          </button>
          <button
            onClick={onClose}
            className="text-sm px-4 py-2.5 rounded-lg border border-border-bright bg-transparent text-text-muted2 transition-colors hover:text-text-primary hover:border-text-muted2"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

interface ModelRowProps {
  agent: AgentType;
  value: string;
  catalog: ModelOption[];
  lookup: Map<string, ModelOption>;
  onChange: (modelId: string) => void;
}

const ModelRow: FC<ModelRowProps> = ({ agent, value, catalog, lookup, onChange }) => {
  const known = lookup.get(value);
  const [isCustom, setIsCustom] = useState(!known && value !== "");

  // If the live catalog refreshes and now contains our saved id, drop out of
  // custom mode automatically.
  useEffect(() => {
    if (lookup.has(value)) setIsCustom(false);
  }, [lookup, value]);

  const handleSelectChange = (next: string) => {
    if (next === CUSTOM_VALUE) {
      setIsCustom(true);
      return;
    }
    setIsCustom(false);
    onChange(next);
  };

  const free = catalog.filter((m) => m.tier === "free");
  const paid = catalog.filter((m) => m.tier === "paid");

  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 items-start">
      <div className="pt-2">
        <div className="text-sm font-medium text-text-primary">{AGENT_LABELS[agent]}</div>
        <div className="text-[11px] text-text-muted leading-snug mt-0.5">
          {AGENT_HINT[agent]}
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <select
          value={isCustom ? CUSTOM_VALUE : value}
          onChange={(e) => handleSelectChange(e.target.value)}
          className="w-full bg-bg-1 border border-border-bright rounded-lg px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-primary"
        >
          {free.length > 0 && (
            <optgroup label={`Free (${free.length})`}>
              {free.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} · {m.context}
                </option>
              ))}
            </optgroup>
          )}
          {paid.length > 0 && (
            <optgroup label={`Paid (${paid.length})`}>
              {paid.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} · {m.context}
                </option>
              ))}
            </optgroup>
          )}
          <option value={CUSTOM_VALUE}>Custom model id…</option>
        </select>
        {isCustom && (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="provider/model-id"
            spellCheck={false}
            autoComplete="off"
            className="w-full bg-bg-1 border border-border-bright rounded-lg px-3 py-2 font-mono text-xs text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-accent-primary"
          />
        )}
      </div>
    </div>
  );
};
