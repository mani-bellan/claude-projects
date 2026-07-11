# Claude Features Demo

This project demonstrates key Claude Code features: hooks, custom commands (skills), agents, and Anthropic API patterns.

## Setup

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY in .env
uv sync  # or: pip install -e .
```

## Project Layout

| Path | Purpose |
|---|---|
| `.claude/settings.json` | Hooks configuration — runs shell scripts on tool events |
| `.claude/commands/` | Custom slash commands available in Claude Code |
| `hooks/` | Shell scripts invoked by the hook system |
| `agents/` | Agent examples using the Anthropic SDK |
| `examples/` | Standalone API feature demos (chat, streaming, tools, vision) |

## Running Examples

```bash
# Basic chat
python examples/01_basic_chat.py

# Streaming
python examples/02_streaming.py

# Tool use
python examples/03_tool_use.py

# Multi-agent orchestration
python agents/multi_agent.py
```

## Hooks

Hooks run shell commands at specific Claude Code lifecycle events. See `.claude/settings.json` and the `hooks/` directory. The hooks in this project:

- **PreToolUse/Bash** — logs every shell command and blocks `rm -rf /`
- **PostToolUse/Edit** — auto-formats Python files with `ruff` after edits
- **Notification** — fires a macOS notification when Claude needs attention
- **Stop** — logs a summary when Claude finishes a task

## Custom Commands

Open Claude Code in this directory and type:

| Command | What it does |
|---|---|
| `/review` | Reviews the current file for bugs, style, and security |
| `/generate-tests` | Generates pytest tests for selected code |
| `/summarize` | Produces a concise summary of any file |
| `/changelog` | Drafts a changelog entry from recent git commits |

## Conventions

- Python 3.11+, managed with `uv`
- All scripts are standalone — no shared state between examples
- API key loaded from `.env` via `python-dotenv`
