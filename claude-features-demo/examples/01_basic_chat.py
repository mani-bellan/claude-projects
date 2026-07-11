"""
01 — Basic Chat

Demonstrates:
- Creating a client
- Sending a single message and reading the response
- Using a system prompt to shape the assistant's persona

Run:
    python examples/01_basic_chat.py
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

response = client.messages.create(
    model=MODEL,
    max_tokens=512,
    system="You are a friendly tutor who explains things simply and concisely.",
    messages=[
        {"role": "user", "content": "Explain what a REST API is in 3 sentences."}
    ],
)

print(response.content[0].text)
