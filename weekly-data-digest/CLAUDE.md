# weekly-data-digest

Generates and emails a weekly digest of the latest developments in the Data field using the Claude API with web search.

## Topics covered

- Data Engineering (dbt, Airflow, Spark, Kafka, Flink)
- ML/AI Engineering (MLOps, model deployment, feature stores)
- LLMs and Generative AI (new models, RAG, agent frameworks)
- Analytics and BI (Metabase, Superset, Looker, visualization)
- Cloud Data Platforms (Snowflake, Databricks, BigQuery, DuckDB, Iceberg)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and SMTP credentials in .env
```

For Gmail, generate an **App Password** (not your regular password):  
→ https://myaccount.google.com/apppasswords

## Run manually

```bash
python digest.py
```

## Schedule weekly (macOS launchd / cron)

**cron** — every Monday at 8 AM:

```
0 8 * * 1 cd /Users/manikandanbellan/Documents/Learn/Claude/weekly-data-digest && /usr/bin/python3 digest.py >> digest.log 2>&1
```

Add with `crontab -e`.

**launchd plist** — create `~/Library/LaunchAgents/com.digest.weekly.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.digest.weekly</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/manikandanbellan/Documents/Learn/Claude/weekly-data-digest/digest.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/manikandanbellan/Documents/Learn/Claude/weekly-data-digest</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>8</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/digest.log</string>
  <key>StandardErrorPath</key><string>/tmp/digest.log</string>
</dict>
</plist>
```

Load it: `launchctl load ~/Library/LaunchAgents/com.digest.weekly.plist`

## How it works

1. Sends the system prompt (cached with `cache_control: ephemeral`) + web_search tool to `claude-sonnet-4-6`
2. Claude searches the web for each topic area and returns structured JSON
3. Script renders HTML + plain-text email and sends via SMTP
