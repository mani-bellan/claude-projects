"""
Weekly Data Field Digest Generator
Searches for latest news across Data Engineering, ML/AI, Analytics, LLMs,
and Cloud Data platforms, then emails a formatted digest.
"""

import os
import smtplib
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SMTP_HOST         = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER         = os.environ["SMTP_USER"]
SMTP_PASSWORD     = os.environ["SMTP_PASSWORD"]
EMAIL_TO          = os.getenv("EMAIL_TO", "mani.bellan@gmail.com")
EMAIL_FROM        = os.getenv("EMAIL_FROM", SMTP_USER)

TOPICS = [
    "Data Engineering (dbt, Airflow, Spark, Kafka, Flink, data pipelines)",
    "ML/AI Engineering (MLOps, model deployment, feature stores, training infra)",
    "LLMs and Generative AI (new models, fine-tuning, RAG, agent frameworks)",
    "Analytics and BI (Metabase, Superset, Looker, data visualization trends)",
    "Cloud Data Platforms (Snowflake, Databricks, BigQuery, DuckDB, Iceberg)",
]

SYSTEM_PROMPT = """You are a senior data engineer and ML practitioner who curates a weekly digest \
of the most important developments in the data ecosystem. Your audience is technical professionals \
who want signal over noise.

Your job:
1. For each topic area provided, use the web_search tool to find the 3-5 most significant \
developments from the past 7 days. Focus on: new product releases, important research papers, \
significant engineering blog posts, and major community discussions.
2. For each item, write a 2-3 sentence summary that explains WHY it matters, not just what it is.
3. Skip minor patch releases, routine vendor marketing, and anything without real technical substance.
4. Return the digest as a JSON object with this exact structure:

{
  "sections": [
    {
      "title": "<topic area name>",
      "items": [
        {
          "headline": "<concise headline>",
          "summary": "<2-3 sentence summary of what it is and why it matters>",
          "source": "<publication or source name>",
          "url": "<url if available, else null>"
        }
      ]
    }
  ],
  "editor_note": "<1-2 sentence overall theme or pattern you noticed this week>"
}

Be selective — quality over quantity. If a topic had a quiet week, 2 items is fine."""


def build_user_message(topics: list[str]) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    topic_list = "\n".join(f"- {t}" for t in topics)
    return (
        f"Today is {today}. Please search for and summarize this week's top developments "
        f"across the following data field topic areas:\n\n{topic_list}\n\n"
        "Search each topic area, then return the full digest as JSON."
    )


def fetch_digest(client: anthropic.Anthropic) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Cache the stable system prompt — saves ~600 tokens per run
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": build_user_message(TOPICS)}],
    )

    # Extract the text block containing JSON
    for block in response.content:
        if block.type == "text":
            text = block.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())

    raise ValueError("No text block found in response")


def render_html(digest: dict, date_str: str) -> str:
    sections_html = ""
    for section in digest.get("sections", []):
        items_html = ""
        for item in section.get("items", []):
            url = item.get("url")
            headline = (
                f'<a href="{url}" style="color:#1a73e8;text-decoration:none;">{item["headline"]}</a>'
                if url
                else item["headline"]
            )
            source = item.get("source", "")
            items_html += f"""
            <div style="margin-bottom:18px;">
              <p style="margin:0 0 4px;font-weight:600;font-size:15px;">{headline}</p>
              <p style="margin:0 0 4px;font-size:14px;color:#444;">{item["summary"]}</p>
              <p style="margin:0;font-size:12px;color:#888;">— {source}</p>
            </div>"""

        sections_html += f"""
        <div style="margin-bottom:32px;">
          <h2 style="font-size:18px;color:#202124;border-bottom:2px solid #e8eaed;padding-bottom:6px;">
            {section["title"]}
          </h2>
          {items_html}
        </div>"""

    editor_note = digest.get("editor_note", "")
    note_block = (
        f"""<div style="background:#f8f9fa;border-left:4px solid #1a73e8;padding:12px 16px;
                        margin-bottom:32px;font-size:14px;color:#444;">
          <strong>Editor's note:</strong> {editor_note}
        </div>"""
        if editor_note
        else ""
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:680px;margin:0 auto;padding:24px;color:#202124;">
  <h1 style="font-size:24px;margin-bottom:4px;">📊 Weekly Data Digest</h1>
  <p style="color:#888;font-size:13px;margin-bottom:24px;">{date_str}</p>
  {note_block}
  {sections_html}
  <hr style="border:none;border-top:1px solid #e8eaed;margin:24px 0;">
  <p style="font-size:12px;color:#aaa;">Generated by weekly-data-digest ·
     <a href="https://github.com/anthropics/anthropic-sdk-python" style="color:#aaa;">Powered by Claude</a>
  </p>
</body>
</html>"""


def render_plain(digest: dict, date_str: str) -> str:
    lines = [f"Weekly Data Digest — {date_str}", "=" * 50, ""]
    note = digest.get("editor_note")
    if note:
        lines += [f"Editor's note: {note}", ""]
    for section in digest.get("sections", []):
        lines += [section["title"], "-" * len(section["title"])]
        for item in section.get("items", []):
            url = item.get("url", "")
            lines += [
                f"• {item['headline']}",
                f"  {item['summary']}",
                f"  Source: {item.get('source', '')}",
            ]
            if url:
                lines.append(f"  {url}")
            lines.append("")
    return "\n".join(lines)


def send_email(subject: str, html_body: str, plain_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())


def main() -> None:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    date_str = datetime.now().strftime("%B %d, %Y")

    print(f"Fetching digest for {date_str}…")
    digest = fetch_digest(client)

    html  = render_html(digest, date_str)
    plain = render_plain(digest, date_str)

    subject = f"📊 Weekly Data Digest — {date_str}"
    print(f"Sending to {EMAIL_TO}…")
    send_email(subject, html, plain)
    print("Done.")


if __name__ == "__main__":
    main()
