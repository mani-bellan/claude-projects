import type { AgentModels, StreamEvent } from "@/types";

export async function* fetchSwarmStream(
  question: string,
  category: string,
  apiKey: string,
  agentModels: AgentModels,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const response = await fetch("/api/swarm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, category, apiKey, agentModels }),
    signal,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error: ${response.status} - ${error}`);
  }
  if (!response.body) {
    throw new Error("No response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            yield JSON.parse(line.slice(6)) as StreamEvent;
          } catch (e) {
            console.error("Failed to parse event:", e);
          }
        }
      }
    }

    if (buffer.startsWith("data: ")) {
      try {
        yield JSON.parse(buffer.slice(6)) as StreamEvent;
      } catch (e) {
        console.error("Failed to parse final event:", e);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
