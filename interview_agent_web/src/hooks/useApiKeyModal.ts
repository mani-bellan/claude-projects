"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "openrouter_api_key";
const LEGACY_KEY = "groq_api_key";

export function useApiKeyModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    if (typeof window === "undefined") return;

    let stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      const legacy = localStorage.getItem(LEGACY_KEY);
      if (legacy && legacy.startsWith("sk-or-")) {
        stored = legacy;
        localStorage.setItem(STORAGE_KEY, legacy);
      }
      if (legacy) localStorage.removeItem(LEGACY_KEY);
    }
    if (stored) setApiKey(stored);
  }, []);

  const open = () => setIsOpen(true);
  const close = () => setIsOpen(false);

  const save = (key: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, key);
    }
    setApiKey(key);
    close();
  };

  return {
    isOpen,
    open,
    close,
    apiKey,
    setApiKey,
    save,
    isMounted,
  };
}
