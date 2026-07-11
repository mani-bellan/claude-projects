"""
Multi-Agent Orchestration — orchestrator + specialist subagents.

Demonstrates:
- An orchestrator agent that breaks a task into subtasks
- Specialist subagents (researcher, writer, critic) each with a focused system prompt
- Passing results between agents
- The "manager ↔ worker" pattern described in the Anthropic agent docs

Pattern:
  User → Orchestrator → [Researcher, Writer] → Orchestrator → Critic → Final answer

Run:
    python agents/multi_agent.py
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Helper: single-turn agent call
# ---------------------------------------------------------------------------


def call_agent(system: str, user: str, max_tokens: int = 1024) -> str:
    """Send a single-turn message to an agent with a given system prompt."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

RESEARCHER_SYSTEM = """
You are a research specialist. Given a topic, produce a concise bullet-point
summary of the key facts, statistics, and perspectives. Be factual and neutral.
Limit your response to 200 words.
"""

WRITER_SYSTEM = """
You are a professional writer. Given research notes, write a clear and engaging
paragraph (100–150 words) suitable for a general audience. Use an active voice.
"""

CRITIC_SYSTEM = """
You are a critical editor. Review the draft below and return:
1. An improved version fixing any clarity, grammar, or factual issues.
2. A one-line critique explaining what you changed and why.
Keep the improved version under 200 words.
"""

ORCHESTRATOR_SYSTEM = """
You are an orchestrator. You coordinate specialist agents to produce high-quality
content. You will receive a topic, call the researcher then the writer, then send
the result for critique. Summarise the final output clearly.
"""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(topic: str) -> dict:
    """Run the full multi-agent pipeline for a given topic."""
    print(f"\n[Orchestrator] Topic: {topic}")

    # Step 1: Research
    print("[Orchestrator] → Calling Researcher agent...")
    research = call_agent(RESEARCHER_SYSTEM, f"Research this topic: {topic}")
    print(f"[Researcher]\n{research}\n")

    # Step 2: Write
    print("[Orchestrator] → Calling Writer agent...")
    draft = call_agent(WRITER_SYSTEM, f"Research notes:\n{research}")
    print(f"[Writer]\n{draft}\n")

    # Step 3: Critique & refine
    print("[Orchestrator] → Calling Critic agent...")
    critique_input = f"Topic: {topic}\n\nDraft:\n{draft}"
    final = call_agent(CRITIC_SYSTEM, critique_input, max_tokens=512)
    print(f"[Critic]\n{final}\n")

    # Step 4: Orchestrator wraps up
    summary = call_agent(
        ORCHESTRATOR_SYSTEM,
        f"Topic: {topic}\nFinal output from critic:\n{final}\n\nPresent the final result to the user.",
    )

    return {"topic": topic, "research": research, "draft": draft, "final": final, "summary": summary}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    topic = "The environmental impact of large language models"
    result = run_pipeline(topic)

    print("=" * 60)
    print("FINAL OUTPUT")
    print("=" * 60)
    print(result["summary"])
