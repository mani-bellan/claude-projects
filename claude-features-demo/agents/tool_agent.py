"""
Tool-Use Agent — filesystem tools with safety guardrails.

Demonstrates:
- Tools that interact with the local filesystem
- A hook-like safety check inside the agent (separate from Claude Code hooks)
- Parallel tool use (Claude can call multiple tools in one response)
- Structured tool output with error handling

Run:
    python agents/tool_agent.py
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Only allow reads within this sandbox directory
SANDBOX = Path(__file__).parent.parent / "examples"

TOOLS = [
    {
        "name": "list_files",
        "description": "List files in the sandbox examples/ directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern, e.g. '*.py'",
                    "default": "*",
                }
            },
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file inside the sandbox examples/ directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename relative to examples/"}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "count_lines",
        "description": "Count the number of lines in a file inside the sandbox examples/ directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename relative to examples/"}
            },
            "required": ["filename"],
        },
    },
]


def _safe_path(filename: str) -> Path:
    """Resolve a filename and raise if it escapes the sandbox."""
    resolved = (SANDBOX / filename).resolve()
    if not str(resolved).startswith(str(SANDBOX.resolve())):
        raise PermissionError(f"Access denied: {filename} is outside the sandbox")
    return resolved


def run_tool(name: str, tool_input: dict) -> str:
    try:
        if name == "list_files":
            pattern = tool_input.get("pattern", "*")
            files = sorted(SANDBOX.glob(pattern))
            return json.dumps([f.name for f in files if f.is_file()])

        if name == "read_file":
            path = _safe_path(tool_input["filename"])
            return path.read_text(encoding="utf-8")

        if name == "count_lines":
            path = _safe_path(tool_input["filename"])
            return str(len(path.read_text(encoding="utf-8").splitlines()))

    except PermissionError as exc:
        return f"BLOCKED: {exc}"
    except FileNotFoundError:
        return f"Error: file not found — {tool_input.get('filename')}"
    except Exception as exc:
        return f"Error: {exc}"

    return f"Unknown tool: {name}"


def run_agent(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "(no text response)"

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [tool] {block.name}({json.dumps(block.input)})")
                result = run_tool(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    questions = [
        "List all Python files in the examples directory.",
        "How many lines are in each example file? Show a table.",
        "Read the file 01_basic_chat.py and briefly explain what it does.",
    ]

    for q in questions:
        print(f"\nUser: {q}")
        print(f"Claude: {run_agent(q)}")
