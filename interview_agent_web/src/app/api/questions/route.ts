import { NextResponse } from "next/server";
import type { Category } from "@/types";

export const runtime = "nodejs";
export const revalidate = 3600;

const MAX_PER_CATEGORY = 30;
const MIN_Q_LEN = 12;
const MAX_Q_LEN = 400;
const FETCH_TIMEOUT_MS = 8000;

const COOKBOOK_SECTION_TO_CATEGORY: Record<string, Category> = {
  python: "coding",
  etl: "coding",
  sql: "sql",
  apis: "architecture",
  integrate: "architecture",
  "message queues": "streaming",
  "distributed message queues": "streaming",
  "message queues (fifo)": "streaming",
  caches: "architecture",
  "data processing": "architecture",
  "stream processing": "streaming",
  "batch processing": "architecture",
  "processing frameworks": "architecture",
  serverless: "architecture",
  "distributed processing frameworks": "architecture",
  scheduling: "architecture",
  airflow: "architecture",
  "ci-cd": "general",
  docker: "general",
  kubernetes: "general",
  "data storage": "architecture",
  "relational databases": "design",
  nosql: "design",
  "analytical stores": "design",
  "relational modeling": "design",
  "dimensional modeling": "design",
  "dimensional data modeling": "design",
  "data lakes": "design",
  "data platforms": "architecture",
  aws: "architecture",
  azure: "architecture",
  gcp: "architecture",
  snowflake: "architecture",
};

type SourceConfig = {
  id: string;
  label: string;
  url: string;
  htmlUrl: string;
} & (
  | { parser: "cookbook"; sectionMap: Record<string, Category> }
  | { parser: "devinterview"; defaultCategory: Category }
);

const SOURCES: SourceConfig[] = [
  {
    id: "cookbook",
    label: "andkret/Cookbook",
    url: "https://raw.githubusercontent.com/andkret/Cookbook/master/sections/08-InterviewQuestions.md",
    htmlUrl:
      "https://github.com/andkret/Cookbook/blob/master/sections/08-InterviewQuestions.md",
    parser: "cookbook",
    sectionMap: COOKBOOK_SECTION_TO_CATEGORY,
  },
  {
    id: "devinterview-de",
    label: "Devinterview · Data Engineer",
    url: "https://raw.githubusercontent.com/Devinterview-io/data-engineer-interview-questions/main/README.md",
    htmlUrl: "https://github.com/Devinterview-io/data-engineer-interview-questions",
    parser: "devinterview",
    defaultCategory: "design",
  },
  {
    id: "devinterview-sql",
    label: "Devinterview · SQL",
    url: "https://raw.githubusercontent.com/Devinterview-io/sql-interview-questions/main/README.md",
    htmlUrl: "https://github.com/Devinterview-io/sql-interview-questions",
    parser: "devinterview",
    defaultCategory: "sql",
  },
  {
    id: "devinterview-spark",
    label: "Devinterview · Apache Spark",
    url: "https://raw.githubusercontent.com/Devinterview-io/apache-spark-interview-questions/main/README.md",
    htmlUrl: "https://github.com/Devinterview-io/apache-spark-interview-questions",
    parser: "devinterview",
    defaultCategory: "architecture",
  },
];

const COOKBOOK_SECTION_RE = /^#{2,4}\s+(.+?)\s*$/;
const COOKBOOK_QUESTION_RE = /^\s*\d+\.\s*\*\*(.+?)\*\*\s*$/;
const DEVINTERVIEW_QUESTION_RE = /^##\s*\d+\.\s+(.+?)\s*$/;

function stripMd(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/(?<!\w)\*(.+?)\*(?!\w)/g, "$1")
    .replace(/(?<!\w)_(.+?)_(?!\w)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function isStreamy(q: string): boolean {
  return /\b(stream|kafka|kinesis|flink|real[- ]?time|structured streaming)\b/i.test(q);
}

function parseCookbook(
  md: string,
  sectionMap: Record<string, Category>
): Partial<Record<Category, string[]>> {
  const out: Partial<Record<Category, string[]>> = {};
  let currentCategory: Category | null = null;

  for (const line of md.split("\n")) {
    const sec = COOKBOOK_SECTION_RE.exec(line);
    if (sec) {
      const name = sec[1].trim().toLowerCase().replace(/\s+/g, " ");
      currentCategory = sectionMap[name] ?? null;
      continue;
    }
    if (!currentCategory) continue;

    const q = COOKBOOK_QUESTION_RE.exec(line);
    if (!q) continue;

    const question = stripMd(q[1]);
    if (question.length < MIN_Q_LEN || question.length > MAX_Q_LEN) continue;

    (out[currentCategory] ??= []).push(question);
  }
  return out;
}

function parseDevinterview(
  md: string,
  defaultCategory: Category
): Partial<Record<Category, string[]>> {
  const out: Partial<Record<Category, string[]>> = {};

  for (const line of md.split("\n")) {
    const q = DEVINTERVIEW_QUESTION_RE.exec(line);
    if (!q) continue;

    const question = stripMd(q[1]);
    if (question.length < MIN_Q_LEN || question.length > MAX_Q_LEN) continue;

    // Light heuristic: route obviously streaming-flavored questions to streaming
    // regardless of the source's default category.
    const category: Category =
      defaultCategory !== "streaming" && isStreamy(question) ? "streaming" : defaultCategory;

    (out[category] ??= []).push(question);
  }
  return out;
}

async function fetchSource(
  source: SourceConfig
): Promise<{
  id: string;
  label: string;
  htmlUrl: string;
  ok: boolean;
  count: number;
  questions: Partial<Record<Category, string[]>>;
  error?: string;
}> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    const response = await fetch(source.url, {
      next: { revalidate: 3600 },
      headers: { Accept: "text/plain" },
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!response.ok) {
      return {
        id: source.id,
        label: source.label,
        htmlUrl: source.htmlUrl,
        ok: false,
        count: 0,
        questions: {},
        error: `HTTP ${response.status}`,
      };
    }

    const md = await response.text();
    const questions =
      source.parser === "cookbook"
        ? parseCookbook(md, source.sectionMap)
        : parseDevinterview(md, source.defaultCategory);

    const count = Object.values(questions).reduce((s, l) => s + (l?.length ?? 0), 0);

    return {
      id: source.id,
      label: source.label,
      htmlUrl: source.htmlUrl,
      ok: true,
      count,
      questions,
    };
  } catch (err) {
    return {
      id: source.id,
      label: source.label,
      htmlUrl: source.htmlUrl,
      ok: false,
      count: 0,
      questions: {},
      error: err instanceof Error ? err.message : "Fetch failed",
    };
  }
}

function mergeAndCap(
  perSource: Partial<Record<Category, string[]>>[]
): Partial<Record<Category, string[]>> {
  const merged: Partial<Record<Category, string[]>> = {};
  const seen = new Set<string>();

  for (const src of perSource) {
    for (const [cat, list] of Object.entries(src) as [Category, string[] | undefined][]) {
      if (!list) continue;
      const bucket = (merged[cat] ??= []);
      for (const q of list) {
        if (bucket.length >= MAX_PER_CATEGORY) break;
        const key = `${cat}::${q.toLowerCase()}`;
        if (seen.has(key)) continue;
        seen.add(key);
        bucket.push(q);
      }
    }
  }
  return merged;
}

export async function GET() {
  const results = await Promise.all(SOURCES.map(fetchSource));
  const questions = mergeAndCap(results.map((r) => r.questions));
  const total = Object.values(questions).reduce((s, l) => s + (l?.length ?? 0), 0);

  if (total === 0) {
    return NextResponse.json(
      {
        error: "All sources returned zero questions",
        sources: results.map(({ questions: _q, ...rest }) => rest),
      },
      { status: 502 }
    );
  }

  return NextResponse.json(
    {
      source: results
        .filter((r) => r.ok)
        .map((r) => r.label)
        .join(" + "),
      sourceUrl: results.find((r) => r.ok)?.htmlUrl ?? "",
      sources: results.map(({ questions: _q, ...rest }) => rest),
      fetchedAt: Date.now(),
      total,
      questions,
    },
    {
      headers: {
        "Cache-Control":
          "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400",
      },
    }
  );
}
