"""
05 — Structured Output

Demonstrates:
- Using a tool with a strict schema to force structured JSON output
- Parsing and working with the structured response
- Using Pydantic for validation (optional, only if installed)

Pattern: define a tool whose sole purpose is to return structured data,
then set tool_choice={"type": "tool", "name": "<tool>"} to force Claude
to always call it.

Run:
    python examples/05_structured_output.py
"""

import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# The "tool" here is really just a schema that shapes the response.
EXTRACT_TOOL = {
    "name": "extract_person",
    "description": "Extract structured information about a person from unstructured text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "occupation": {"type": "string"},
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of skills or areas of expertise",
            },
            "location": {"type": "string"},
        },
        "required": ["name", "occupation"],
    },
}


def extract_person(text: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "extract_person"},
        messages=[{"role": "user", "content": f"Extract person info from this text:\n\n{text}"}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    return {}


if __name__ == "__main__":
    texts = [
        "Dr. Sarah Chen, 34, is a machine learning engineer at a startup in San Francisco. She specialises in NLP, computer vision, and distributed systems.",
        "Meet Marcus — a 28-year-old freelance graphic designer based in Berlin. He's been crafting brand identities, UI mockups, and motion graphics for 6 years.",
    ]

    for text in texts:
        print(f"Input:\n  {text}\n")
        result = extract_person(text)
        print(f"Extracted:\n{json.dumps(result, indent=2)}\n{'─' * 50}\n")
