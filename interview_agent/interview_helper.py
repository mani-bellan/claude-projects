"""
Data Engineering Interview Agent Swarm
=======================================
A multi-agent platform that:
  1. Reads & analyzes your DE interview question
  2. Produces a full solution
  3. Validates it for correctness, edge cases, and complexity
  4. Optimizes it with final Big-O analysis

Requirements:
    pip install groq rich

Usage:
    export GROQ_API_KEY="gsk_your_key_here"   # free at console.groq.com
    python de_interview_swarm.py

    # Or pass a question directly:
    python de_interview_swarm.py --question "Write a Python function to find top-K frequent elements"
    python de_interview_swarm.py --category sql --question "Find the second highest salary per department"
    python de_interview_swarm.py --file my_questions.txt   # run on a file of questions (one per line)
"""

import os
import sys
import time
import argparse
import concurrent.futures
from pathlib import Path
from datetime import datetime

try:
    from groq import Groq
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError:
    print("\n[ERROR] Missing dependencies. Run:\n\n    pip install groq rich\n")
    sys.exit(1)

console = Console()

# ── Model config ──────────────────────────────────────────────────────────────

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 2048

CATEGORIES = ["coding", "architecture", "design", "sql", "streaming", "general"]

EXAMPLE_QUESTIONS = {
    "coding": [
        "Write a Python function to find the top-K most frequent elements in a stream of data efficiently.",
        "Implement a sliding window to compute the average of the last N records in O(1) time.",
        "Write a function to deduplicate records in a large dataset using hashing.",
    ],
    "architecture": [
        "Design a real-time data pipeline to ingest 1 million events/second from IoT devices.",
        "How would you architect a Lambda architecture for batch + streaming analytics?",
        "Design a fault-tolerant ETL system that handles schema changes gracefully.",
    ],
    "design": [
        "Design a data warehouse schema for an e-commerce platform.",
        "How would you design a slowly changing dimension (SCD Type 2) for a customer table?",
        "Design a system to handle late-arriving data in a streaming pipeline.",
    ],
    "sql": [
        "Write a SQL query to find the second highest salary per department.",
        "How would you compute a 7-day rolling average of daily sales in SQL?",
        "Write a query to detect gaps in a time series sensor dataset.",
    ],
    "streaming": [
        "How does Apache Kafka handle message ordering and consumer group rebalancing?",
        "Compare Flink vs Spark Streaming for exactly-once semantics.",
        "How would you implement deduplication in a Kafka Streams application?",
    ],
}

# ── Agent prompts ─────────────────────────────────────────────────────────────

AGENT_READER_PROMPT = """You are a data engineering interview question analyst.
Given a question, extract:
1. CATEGORY: (coding/architecture/design/sql/streaming)
2. DIFFICULTY: (easy/medium/hard)
3. KEY CONCEPTS: list the main DE concepts being tested
4. CONSTRAINTS: any explicit constraints mentioned
5. EXPECTED OUTPUT: what a complete answer should include

Be concise and structured."""

AGENT_SOLVER_PROMPT = """You are an expert data engineer solving interview questions.
Produce a thorough solution:
- For CODING: write complete, working Python code with explanation
- For ARCHITECTURE/DESIGN: describe the system with components, data flow, and trade-offs
- For SQL: write the full query with explanation of the logic
- For STREAMING: explain concepts and provide code or pseudocode where relevant

Always include:
1. APPROACH: high-level strategy
2. SOLUTION: full code or detailed design
3. INITIAL COMPLEXITY: state your initial time and space complexity estimate
4. EDGE CASES: list edge cases you considered"""

AGENT_VALIDATOR_PROMPT = """You are a senior data engineer and code reviewer.
Critically validate the proposed solution. Check for:
1. CORRECTNESS: Does it solve the problem? Any logical errors?
2. TIME COMPLEXITY: Is the stated complexity correct? Can it be improved?
3. SPACE COMPLEXITY: Is memory usage optimal? Any hidden space costs?
4. EDGE CASES: What edge cases are NOT handled?
5. SCALABILITY: Will it work at scale (millions of rows, distributed systems)?
6. CODE QUALITY: Python anti-patterns, inefficiencies, missing error handling?
7. ISSUES FOUND: List specific problems with severity (critical/major/minor)

Be specific and precise. This is for an interview context."""

AGENT_OPTIMIZER_PROMPT = """You are a principal data engineer and algorithm optimization expert.
Based on the validation report, produce a FINAL OPTIMIZED SOLUTION.

Your response MUST include these exact sections:

## FINAL SOLUTION
[Complete, production-ready code or design — fix ALL issues from validation]

## TIME COMPLEXITY
[Big-O analysis of the optimized solution with explanation of best/average/worst case]

## SPACE COMPLEXITY
[Big-O analysis of memory usage with explanation]

## OPTIMIZATIONS MADE
[Bullet list of each specific improvement over the original]

## INTERVIEW TIPS
[2-3 key points to mention in an interview to impress the interviewer]

Do not skip any section. Code must be clean, readable, and production-grade."""

# ── Groq client ───────────────────────────────────────────────────────────────

def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        console.print("\n[bold red]GROQ_API_KEY not set.[/bold red]")
        console.print("Get a free key at [link=https://console.groq.com]https://console.groq.com[/link]")
        console.print("Then run:\n\n    export GROQ_API_KEY='gsk_your_key_here'\n")
        sys.exit(1)
    return Groq(api_key=api_key)


def call_agent(client: Groq, system_prompt: str, user_content: str, agent_name: str) -> str:
    """Call a single agent and return its output."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.3,
            max_tokens=MAX_TOKENS,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERROR in {agent_name}]: {e}"

# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_swarm(client: Groq, question: str, category: str = "general") -> dict:
    """Run the full 4-agent swarm sequentially and return all outputs."""

    results = {}

    steps = [
        ("reader",    "Question reader",    "[blue]Analyzing question...[/blue]"),
        ("solver",    "Solution producer",  "[magenta]Producing solution...[/magenta]"),
        ("validator", "Validator",          "[green]Validating solution...[/green]"),
        ("optimizer", "Optimizer",          "[yellow]Optimizing...[/yellow]"),
    ]

    for step_id, step_name, status_msg in steps:
        console.print(f"\n{'─'*60}")
        console.print(f"  [bold]{step_name}[/bold]  {status_msg}")
        console.print(f"{'─'*60}")

        start = time.time()

        if step_id == "reader":
            output = call_agent(
                client,
                AGENT_READER_PROMPT,
                f"Question (category hint: {category}):\n{question}",
                step_name,
            )

        elif step_id == "solver":
            output = call_agent(
                client,
                AGENT_SOLVER_PROMPT,
                f"Question: {question}\n\nAnalysis:\n{results['reader']}",
                step_name,
            )

        elif step_id == "validator":
            output = call_agent(
                client,
                AGENT_VALIDATOR_PROMPT,
                f"Original question: {question}\n\nProposed solution:\n{results['solver']}",
                step_name,
            )

        elif step_id == "optimizer":
            output = call_agent(
                client,
                AGENT_OPTIMIZER_PROMPT,
                (
                    f"Question: {question}\n\n"
                    f"Original solution:\n{results['solver']}\n\n"
                    f"Validation issues:\n{results['validator']}"
                ),
                step_name,
            )

        elapsed = time.time() - start
        results[step_id] = output
        console.print(output)
        console.print(f"\n[dim]✓ {step_name} completed in {elapsed:.1f}s[/dim]")

    return results


def extract_section(text: str, heading: str) -> str:
    """Extract a ## HEADING section from markdown text."""
    import re
    pattern = rf"##\s*{re.escape(heading)}\s*\n([\s\S]*?)(?=\n##|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def print_summary(results: dict, question: str, category: str) -> None:
    """Print a formatted summary panel after the swarm completes."""
    optimizer_out = results.get("optimizer", "")
    time_c  = extract_section(optimizer_out, "TIME COMPLEXITY")
    space_c = extract_section(optimizer_out, "SPACE COMPLEXITY")
    tips    = extract_section(optimizer_out, "INTERVIEW TIPS")

    console.print("\n")
    console.print(Panel(
        f"[bold]Question:[/bold] {question[:120]}{'…' if len(question) > 120 else ''}\n"
        f"[bold]Category:[/bold] {category}",
        title="[bold cyan]Swarm complete[/bold cyan]",
        box=box.ROUNDED,
    ))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("", style="bold")
    table.add_column("")
    if time_c:
        table.add_row("⏱  Time complexity",  time_c.split('\n')[0][:80])
    if space_c:
        table.add_row("💾 Space complexity", space_c.split('\n')[0][:80])
    console.print(table)

    if tips:
        console.print(Panel(tips, title="[bold yellow]Interview tips[/bold yellow]", box=box.SIMPLE))


def save_output(results: dict, question: str, category: str) -> Path:
    """Save the full swarm output to a markdown file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"de_solution_{category}_{timestamp}.md"
    path = Path(filename)

    optimizer_out = results.get("optimizer", "")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# DE Interview Solution\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Category:** {category}  \n")
        f.write(f"**Model:** {MODEL}  \n\n")
        f.write(f"---\n\n## Question\n\n{question}\n\n---\n\n")
        f.write(f"## Question Analysis\n\n{results.get('reader', '')}\n\n---\n\n")
        f.write(f"## Initial Solution\n\n{results.get('solver', '')}\n\n---\n\n")
        f.write(f"## Validation Report\n\n{results.get('validator', '')}\n\n---\n\n")
        f.write(f"## Final Optimized Solution\n\n{optimizer_out}\n")

    return path

# ── Interactive mode ──────────────────────────────────────────────────────────

def pick_category() -> str:
    console.print("\n[bold]Select category:[/bold]")
    for i, cat in enumerate(CATEGORIES, 1):
        console.print(f"  {i}. {cat}")
    while True:
        choice = input("\nEnter number (or press Enter for 'general'): ").strip()
        if not choice:
            return "general"
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            return CATEGORIES[int(choice) - 1]
        console.print("[red]Invalid choice, try again.[/red]")


def show_examples(category: str) -> None:
    examples = EXAMPLE_QUESTIONS.get(category, [])
    if examples:
        console.print(f"\n[dim]Example {category} questions:[/dim]")
        for i, ex in enumerate(examples, 1):
            console.print(f"  [dim]{i}. {ex}[/dim]")


def interactive_mode(client: Groq) -> None:
    console.print(Panel(
        "[bold]Data Engineering Interview Agent Swarm[/bold]\n"
        "4 agents: analyze → solve → validate → optimize",
        box=box.ROUNDED,
    ))

    while True:
        category = pick_category()
        show_examples(category)

        console.print("\n[bold]Enter your question[/bold] (or 'quit' to exit):")
        question = input("> ").strip()

        if question.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if not question:
            console.print("[red]Question cannot be empty.[/red]")
            continue

        results = run_swarm(client, question, category)
        print_summary(results, question, category)

        save = input("\nSave to markdown file? (y/N): ").strip().lower()
        if save == "y":
            path = save_output(results, question, category)
            console.print(f"[green]Saved to {path}[/green]")

        again = input("\nRun another question? (Y/n): ").strip().lower()
        if again == "n":
            console.print("[dim]Goodbye![/dim]")
            break

# ── Batch mode ────────────────────────────────────────────────────────────────

def batch_mode(client: Groq, file_path: str, category: str) -> None:
    """Run swarm on every question in a text file (one per line)."""
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        sys.exit(1)

    questions = [q.strip() for q in path.read_text().splitlines() if q.strip()]
    console.print(f"\n[bold]Batch mode:[/bold] {len(questions)} questions from {file_path}\n")

    for i, question in enumerate(questions, 1):
        console.print(f"\n[bold cyan]═══ Question {i}/{len(questions)} ═══[/bold cyan]")
        results = run_swarm(client, question, category)
        print_summary(results, question, category)
        out_path = save_output(results, question, category)
        console.print(f"[green]Saved → {out_path}[/green]")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Data Engineering Interview Agent Swarm (powered by Groq + Llama 3.3 70B)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--question",  "-q", help="Question to solve directly")
    parser.add_argument("--category",  "-c", choices=CATEGORIES, default="general",
                        help="Question category (default: general)")
    parser.add_argument("--file",      "-f", help="Text file with one question per line (batch mode)")
    parser.add_argument("--save",      "-s", action="store_true",
                        help="Auto-save output to markdown file")
    args = parser.parse_args()

    client = get_client()

    if args.file:
        batch_mode(client, args.file, args.category)

    elif args.question:
        results = run_swarm(client, args.question, args.category)
        print_summary(results, args.question, args.category)
        if args.save:
            path = save_output(results, args.question, args.category)
            console.print(f"[green]Saved to {path}[/green]")

    else:
        interactive_mode(client)


if __name__ == "__main__":
    main()