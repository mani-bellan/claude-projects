import type { Category } from "@/types";

export const CATEGORIES = ["coding", "architecture", "design", "sql", "streaming", "general"] as const;

export type Mode = "code" | "concept";

export const MODE_BY_CATEGORY: Record<Category, Mode> = {
  coding: "code",
  sql: "code",
  architecture: "concept",
  design: "concept",
  streaming: "concept",
  general: "concept",
};

export function getMode(category: Category): Mode {
  return MODE_BY_CATEGORY[category];
}

export const EXAMPLE_QUESTIONS = {
  coding: [
    "Write a Python function to find the top-K most frequent elements in a stream of data efficiently.",
    "Implement a sliding window to compute the average of the last N records in O(1) time.",
    "Write a function to deduplicate records in a large dataset using hashing.",
  ],
  architecture: [
    "Design a real-time data pipeline to ingest 1 million events/second from IoT devices.",
    "How would you architect a Lambda architecture for batch + streaming analytics?",
    "Design a fault-tolerant ETL system that handles schema changes gracefully.",
  ],
  design: [
    "Design a data warehouse schema for an e-commerce platform.",
    "How would you design a slowly changing dimension (SCD Type 2) for a customer table?",
    "Design a system to handle late-arriving data in a streaming pipeline.",
  ],
  sql: [
    "Write a SQL query to find the second highest salary per department.",
    "How would you compute a 7-day rolling average of daily sales in SQL?",
    "Write a query to detect gaps in a time series sensor dataset.",
  ],
  streaming: [
    "How does Apache Kafka handle message ordering and consumer group rebalancing?",
    "Compare Flink vs Spark Streaming for exactly-once semantics.",
    "How would you implement deduplication in a Kafka Streams application?",
  ],
  general: [
    "What is the difference between batch and streaming data processing?",
    "Explain the CAP theorem and its implications for distributed systems.",
    "What are the trade-offs between normalization and denormalization in databases?",
  ],
};

export const AGENT_CONFIG = {
  reader: {
    name: "Question Reader",
    color: "text-semantic-reader",
    bgColor: "bg-blue-500/10",
    borderColor: "border-semantic-reader",
    icon: "📖",
  },
  solver: {
    name: "Solution Producer",
    color: "text-semantic-solver",
    bgColor: "bg-purple-500/10",
    borderColor: "border-semantic-solver",
    icon: "💡",
  },
  validator: {
    name: "Validator",
    color: "text-semantic-validator",
    bgColor: "bg-green-500/10",
    borderColor: "border-semantic-validator",
    icon: "✓",
  },
  optimizer: {
    name: "Optimizer",
    color: "text-semantic-optimizer",
    bgColor: "bg-amber-500/10",
    borderColor: "border-semantic-optimizer",
    icon: "⚡",
  },
};

export const MODEL = "llama-3.3-70b-versatile";
export const MAX_TOKENS = 2048;
