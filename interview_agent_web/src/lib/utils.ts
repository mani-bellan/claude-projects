export function extractSection(text: string, heading: string): string {
  const regex = new RegExp(`##\\s*${heading}\\s*\\n([\\s\\S]*?)(?=\\n##|$)`, "i");
  const match = text.match(regex);
  return match ? match[1].trim() : "";
}

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function formatElapsed(ms: number): string {
  const seconds = (ms / 1000).toFixed(1);
  return `${seconds}s`;
}

export function truncateText(text: string, length: number): string {
  if (text.length <= length) return text;
  return text.substring(0, length) + "…";
}

export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

export function saveAsMarkdown(
  content: {
    question: string;
    category: string;
    results: Record<string, string>;
    timestamp: number;
  }
): void {
  const markdown = `# DE Interview Helper — Solution

**Date:** ${new Date(content.timestamp).toLocaleString()}
**Category:** ${content.category}
**Provider:** OpenRouter (per-agent models)

---

## Question

${content.question}

---

## Question Analysis

${content.results.reader}

---

## Initial Solution

${content.results.solver}

---

## Validation Report

${content.results.validator}

---

## Final Optimized Solution

${content.results.optimizer}
`;

  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `de_solution_${content.category}_${Date.now()}.md`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
