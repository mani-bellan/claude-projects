"""
04 — Vision (Image Input)

Demonstrates:
- Sending images to Claude as base64-encoded content blocks
- Sending images via public URL
- Asking questions about images
- Mixing text and image content in a single message

Run:
    python examples/04_vision.py

Note: The script uses a public image URL so no local image file is needed.
"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# ---------------------------------------------------------------------------
# Example 1: Image from URL
# ---------------------------------------------------------------------------

print("=== Vision via URL ===\n")

response = client.messages.create(
    model=MODEL,
    max_tokens=512,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/240px-PNG_transparency_demonstration_1.png",
                    },
                },
                {
                    "type": "text",
                    "text": "Describe this image in one sentence.",
                },
            ],
        }
    ],
)

print(response.content[0].text)

# ---------------------------------------------------------------------------
# Example 2: Multiple images in one message
# ---------------------------------------------------------------------------

print("\n=== Multiple images ===\n")

response = client.messages.create(
    model=MODEL,
    max_tokens=512,
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "I'm going to show you two images. Please compare them briefly."},
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/240px-PNG_transparency_demonstration_1.png",
                    },
                },
                {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg",
                    },
                },
                {"type": "text", "text": "What is different between these two images?"},
            ],
        }
    ],
)

print(response.content[0].text)
