# pr-toolkit

PR review tools. Use them individually or run them all via `/review-pr`.

| Component | Triggered by |
|---|---|
| `silent-failure-hunter` agent | Diffs touching catch/try blocks, fallback patterns, default values |
| `test-coverage-analyzer` agent | "Are the tests thorough?" "Test coverage on this PR" |
| `type-design-analyzer` agent | New types, refactored data models, "review these types" |
| `/review-pr` command | Run all three in parallel against current branch or specified PR |

Complements `core-skills/code-review` which covers the general case. These agents focus on specific failure modes that generic review tends to miss.
