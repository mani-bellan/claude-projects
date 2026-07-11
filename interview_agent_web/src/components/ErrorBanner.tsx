"use client";

import type { FC } from "react";
import { AlertIcon, CloseIcon } from "./icons";

interface ErrorBannerProps {
  error: string | null;
  onDismiss?: () => void;
}

export const ErrorBanner: FC<ErrorBannerProps> = ({ error, onDismiss }) => {
  if (!error) return null;

  return (
    <div
      role="alert"
      className="bg-semantic-danger/10 border border-semantic-danger/30 rounded-lg px-4 py-3 text-sm text-semantic-danger mb-4 flex items-start gap-3"
    >
      <AlertIcon width={16} height={16} className="mt-0.5 flex-shrink-0" />
      <span className="flex-1 text-text-secondary">{error}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          className="text-semantic-danger hover:opacity-80 transition-opacity"
        >
          <CloseIcon width={14} height={14} />
        </button>
      )}
    </div>
  );
};
