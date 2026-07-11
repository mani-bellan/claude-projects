"""
03 — Tool Use (Function Calling)

Demonstrates:
- Defining tools with JSON Schema
- Handling stop_reason == "tool_use"
- Returning tool results and getting the final answer
- Using bespoke_tools / force_tool_choice

Run:
    python examples/03_tool_use.py
"""

import json
import os
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

TOOLS = [
    {
        "name": "get_current_time",
        "description": "Returns the current UTC date and time.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "unit_convert",
        "description": "Convert a value between units.",
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "from_unit": {"type": "string", "description": "e.g. 'km', 'miles', 'kg', 'lbs'"},
                "to_unit": {"type": "string"},
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
]

CONVERSION_FACTORS = {
    ("km", "miles"): 0.621371,
    ("miles", "km"): 1.60934,
    ("kg", "lbs"): 2.20462,
    ("lbs", "kg"): 0.453592,
    ("c", "f"): None,  # handled specially
    ("f", "c"): None,
}


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_current_time":
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if name == "unit_convert":
        value = tool_input["value"]
        from_unit = tool_input["from_unit"].lower()
        to_unit = tool_input["to_unit"].lower()

        if (from_unit, to_unit) == ("c", "f"):
            return f"{value * 9/5 + 32:.2f} °F"
        if (from_unit, to_unit) == ("f", "c"):
            return f"{(value - 32) * 5/9:.2f} °C"

        factor = CONVERSION_FACTORS.get((from_unit, to_unit))
        if factor:
            return f"{value * factor:.4f} {to_unit}"
        return f"Unsupported conversion: {from_unit} → {to_unit}"

    return f"Unknown tool: {name}"


def ask(question: str) -> str:
    messages = [{"role": "user", "content": question}]

    response = client.messages.create(model=MODEL, max_tokens=512, tools=TOOLS, messages=messages)
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  → Tool call: {block.name}({json.dumps(block.input)})")
                result = execute_tool(block.name, block.input)
                print(f"  → Result: {result}")
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(model=MODEL, max_tokens=512, tools=TOOLS, messages=messages)

    return response.content[0].text


if __name__ == "__main__":
    questions = [
        "What time is it right now?",
        "Convert 100 km to miles.",
        "What is 37°C in Fahrenheit?",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        print(f"A: {ask(q)}")
