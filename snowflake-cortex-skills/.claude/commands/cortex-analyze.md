Generate Snowflake SQL that applies one or more Cortex analysis functions to the column or table described in $ARGUMENTS.

Available functions to consider (apply whichever fit the request):

| Function | Use when |
|---|---|
| `SNOWFLAKE.CORTEX.SENTIMENT(col)` | Scoring customer feedback, reviews, tickets |
| `SNOWFLAKE.CORTEX.SUMMARIZE(col)` | Condensing long documents, call transcripts, emails |
| `SNOWFLAKE.CORTEX.TRANSLATE(col, src_lang, tgt_lang)` | Multi-language datasets |
| `SNOWFLAKE.CORTEX.CLASSIFY_TEXT(col, ARRAY_CONSTRUCT(...))` | Routing, tagging, zero-shot classification |
| `SNOWFLAKE.CORTEX.EXTRACT_ANSWER(context_col, question)` | Structured QA over free-text fields |
| `SNOWFLAKE.CORTEX.COMPLETE(model, prompt_col)` | Custom analysis via LLM |

Output:
1. A fenced ```sql block — SELECT with the original columns plus each analysis function result as a new aliased column
2. Brief explanation of why each function was chosen
3. A note on any language codes required (ISO 639-1) for TRANSLATE
4. A downstream aggregation example — e.g., `AVG(sentiment_score)` grouped by category
