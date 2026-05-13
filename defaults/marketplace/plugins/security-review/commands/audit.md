---
description: Run a security audit on the current diff (or specified scope) using the security-reviewer agent.
---

Dispatch the security-reviewer agent. Scope from $ARGUMENTS — could be a path, a git ref range, or "this PR". If empty, default to `git diff HEAD~1` (last commit) or the current branch's diff against main, whichever is more useful.

Show the agent's findings as-is. If no CRITICAL/HIGH findings, say so explicitly so the user knows the audit ran and was clean.
