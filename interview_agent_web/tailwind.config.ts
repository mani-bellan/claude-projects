import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          0: "#0a0d14",
          1: "#0f1320",
          2: "#151a29",
          3: "#1c2235",
        },
        border: {
          DEFAULT: "rgba(148,163,184,0.08)",
          bright: "rgba(148,163,184,0.16)",
          accent: "rgba(99,102,241,0.35)",
        },
        accent: {
          primary: "#6366f1",
          hover: "#818cf8",
          subtle: "rgba(99,102,241,0.12)",
          blue: "#38bdf8",
          amber: "#f59e0b",
          purple: "#a78bfa",
          success: "#10b981",
        },
        text: {
          primary: "#e2e8f0",
          secondary: "#cbd5e1",
          muted: "#64748b",
          muted2: "#94a3b8",
        },
        semantic: {
          reader: "#38bdf8",
          solver: "#a78bfa",
          validator: "#34d399",
          optimizer: "#fbbf24",
          danger: "#f87171",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      letterSpacing: {
        tightish: "-0.01em",
      },
      animation: {
        pulse: "pulse 1.4s ease-in-out infinite",
        spin: "spin 0.7s linear infinite",
        "fade-in": "fadeIn 200ms ease-out",
      },
      boxShadow: {
        soft: "0 1px 0 rgba(255,255,255,0.04) inset, 0 1px 2px rgba(0,0,0,0.3)",
        glow: "0 0 0 1px rgba(99,102,241,0.35), 0 8px 24px -8px rgba(99,102,241,0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
