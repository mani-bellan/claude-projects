"""
02 — Streaming Responses

Demonstrates:
- Using client.messages.stream() for real-time token output
- The context manager pattern for streaming
- Accessing the final message after the stream closes

Run:
    python examples/02_streaming.py
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

print("Streaming response:\n")

with client.messages.stream(
    model=MODEL,
    max_tokens=512,
    messages=[
        {
            "role": "user",
            "content": "Write a short poem about the joy of building software, in 8 lines.",
        }
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

# Access aggregated final message after stream ends
final = stream.get_final_message()
print(f"\n\n[stop_reason: {final.stop_reason}]")
print(f"[input_tokens: {final.usage.input_tokens}, output_tokens: {final.usage.output_tokens}]")
