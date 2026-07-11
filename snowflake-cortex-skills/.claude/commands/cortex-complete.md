Generate a Snowflake SQL snippet that calls SNOWFLAKE.CORTEX.COMPLETE() based on the task described in $ARGUMENTS.

Steps to follow:

1. **Choose a model** — pick the best-fit model for the task:
   - General reasoning / long context → `llama3.1-70b` or `mistral-large2`
   - Speed-sensitive batch jobs → `snowflake-arctic` or `mixtral-8x7b`
   - Coding tasks → `llama3-70b`
   - Explain your choice.

2. **Prompt engineering** — write a clear system prompt and user prompt. Use Snowflake string concatenation (`||`) to inject column values into the prompt.

3. **Output parsing** — if the response should be structured (JSON, list, etc.), add a `TRY_PARSE_JSON()` wrapper and explain the schema.

4. **Batch pattern** — wrap the call in a `SELECT` over a table so it processes every row.

5. **Cost note** — mention that each COMPLETE call consumes Cortex credits; suggest running on a sampled table during development.

Output:
- A fenced ```sql block with the complete query
- Explanation of prompt design and model choice
- Example output row showing what the response column looks like
