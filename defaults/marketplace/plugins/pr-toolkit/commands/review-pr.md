---
description: Run a full PR review — dispatch silent-failure-hunter, test-coverage-analyzer, and type-design-analyzer in parallel against the current branch's diff (or a specified PR).
---

Run a comprehensive PR review. Use $ARGUMENTS as the PR identifier (number, URL, or branch); if empty, review the current branch against its merge base with `main`.

Dispatch three subagents IN PARALLEL (one message, three Agent tool calls):

1. `silent-failure-hunter` — flag swallowed errors, fallback logic that masks bugs
2. `test-coverage-analyzer` — identify gaps in test coverage for the changes
3. `type-design-analyzer` — evaluate types introduced or modified

When all three return, synthesize a single report:

```
=== PR review ===

Critical issues (block merge):
- ...

Suggestions:
- ...

Test coverage gaps:
- ...

Type design:
- ...
```

Lead with critical. If no critical issues, say so explicitly.
