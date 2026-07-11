"""
Simple Agent — an agentic loop with tool use.

Demonstrates:
- Defining custom tools as JSON schemas
- Running an agentic loop: send messages → handle tool calls → send results → repeat
- Stopping when the model returns end_turn (no more tool calls)

Run:
    python agents/simple_agent.py
"""

import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "calculator",
        "description": "Evaluate a mathematical expression and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A valid Python math expression, e.g. '2 ** 10 + 42'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Return a mocked current weather report for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"}
            },
            "required": ["city"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def run_tool(name: str, tool_input: dict) -> str:
    if name == "calculator":
        try:
            # Safe eval: only allow math operations
            allowed = {k: v for k, v in vars(__builtins__).items() if k in {"abs", "round", "min", "max", "pow"}}  # type: ignore[arg-type]
            result = eval(tool_input["expression"], {"__builtins__": allowed})  # noqa: S307
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"

    if name == "get_weather":
        city = tool_input["city"]
        # Mocked responses — replace with a real weather API call
        mock_data = {
            "Tokyo": "Sunny, 22°C, humidity 60%",
            "London": "Overcast, 14°C, humidity 80%",
            "New York": "Partly cloudy, 18°C, humidity 55%",
        }
        return mock_data.get(city, f"No weather data available for {city}")

    return f"Unknown tool: {name}"


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


def run_agent(user_message: str) -> str:
    """Send a message and loop until the model is done (no more tool calls)."""
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract the final text reply
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "(no text response)"

        # Handle tool use
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [tool] {block.name}({json.dumps(block.input)})")
                result = run_tool(block.name, block.input)
                print(f"  [result] {result}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    queries = [
        "What is 2 to the power of 16, divided by 7? Round to 2 decimal places.",
        "What's the weather like in Tokyo and London today?",
        "If I fly from New York to Tokyo, what is the temperature difference?",
    ]

    for query in queries:
        print(f"\nUser: {query}")
        answer = run_agent(query)
        print(f"Claude: {answer}")
