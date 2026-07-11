Review the file at $ARGUMENTS (or the file currently open in the editor if no argument is given).

Produce a structured code review covering:

1. **Bugs & correctness** — logic errors, off-by-ones, unhandled exceptions, race conditions
2. **Security** — injection risks, exposed secrets, insecure defaults, OWASP Top 10 issues
3. **Readability** — naming, unnecessary complexity, missing context
4. **Performance** — obvious bottlenecks, unnecessary allocations, N+1 queries

Format the output as a markdown report with a section per category. List each finding as:
- **Severity** (critical / high / medium / low / info)
- **Location** (file:line)
- **Issue** and **Suggested fix**

End with an overall score out of 10 and a one-line verdict.
