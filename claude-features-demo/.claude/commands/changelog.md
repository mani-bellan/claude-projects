Draft a changelog entry for the most recent git commits.

Steps:
1. Run `git log --oneline -20` to see recent commits
2. Run `git diff HEAD~5..HEAD --stat` to understand the scope of changes
3. Group changes into conventional changelog categories: **Added**, **Changed**, **Fixed**, **Removed**, **Security**
4. Write the entry in [Keep a Changelog](https://keepachangelog.com) format for today's date
5. Keep each bullet concise (one line) and written from the user's perspective — what changed, not how

Output only the markdown changelog block, ready to paste into CHANGELOG.md.
