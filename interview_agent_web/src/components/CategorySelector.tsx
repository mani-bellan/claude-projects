"use client";

import { CATEGORIES } from "@/lib/constants";
import type { Category } from "@/types";
import type { FC } from "react";

const CATEGORY_DOT: Record<Category, string> = {
  coding: "bg-semantic-solver",
  architecture: "bg-semantic-reader",
  design: "bg-semantic-validator",
  sql: "bg-semantic-optimizer",
  streaming: "bg-accent-purple",
  general: "bg-text-muted",
};

const CATEGORY_LABEL: Record<Category, string> = {
  coding: "Coding",
  architecture: "Architecture",
  design: "Design",
  sql: "SQL",
  streaming: "Streaming",
  general: "General",
};

interface CategorySelectorProps {
  selected: Category;
  onChange: (category: Category) => void;
}

export const CategorySelector: FC<CategorySelectorProps> = ({ selected, onChange }) => {
  return (
    <div className="bg-bg-2 border border-border rounded-xl overflow-hidden shadow-soft">
      <div className="px-4 py-2.5 border-b border-border text-xs font-medium text-text-secondary">
        Category
      </div>
      <div className="p-2 flex flex-col gap-0.5">
        {CATEGORIES.map((cat) => {
          const isSelected = selected === cat;
          return (
            <button
              key={cat}
              onClick={() => onChange(cat)}
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors border ${
                isSelected
                  ? "bg-bg-1 border-border-bright text-text-primary"
                  : "border-transparent text-text-muted2 hover:bg-bg-1 hover:text-text-primary"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${CATEGORY_DOT[cat]}`} />
              <span className="flex-1 text-left">{CATEGORY_LABEL[cat]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
