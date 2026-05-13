---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing — before committing, before creating PRs, before saying "done". Requires running the verification commands and confirming output before any success claim. Evidence before assertions, always.
---

# verification-before-completion

"I've finished" is a claim. Claims need evidence. This skill prevents the most common LLM failure mode: declaring success without running the verification that would expose the failure.

## When to act

- About to say "done", "fixed", "passing", "complete", "ready"
- About to commit or open a PR
- About to mark a task complete in tracking
- About to describe work as finished in conversation

## When not to act

- Mid-task — verification interrupts flow; do it at completion boundaries
- For exploratory or research work where "done" isn't the right frame

## The pipeline

### 1. Run the actual verification

Don't reason about whether it would pass. Run it. Common verifications:
- The test suite: `pytest`, `npm test`, `cargo test`, etc.
- The type checker: `mypy`, `tsc`, `cargo check`
- The linter: `ruff`, `eslint`, etc.
- The build: `cargo build`, `npm run build`
- The thing the user asked about: if they said "make X work", actually do X

### 2. Read the output

Not just the exit code. Read the actual output. Common traps:
- A test suite that passed but skipped the test you cared about
- A build that succeeded with deprecation warnings that will break in the next version
- A lint pass that ignored a file via config

### 3. Confirm the original ask

Compare what was asked to what you have:
- The user asked for X. Does the verification cover X?
- If X is a UI change: did you actually look at the UI, or just verify the code compiles?
- If X is a behavior change: does a test exercise the new behavior, or just the changed code path?

### 4. If verification fails, say so

The fix to verification failure is *not* to suppress the failure. It's to report it and continue working. The user would rather see "tests fail because of X, working on it" than "done" followed by a broken merge.

## Output discipline

When reporting completion, include the verification you actually ran:

> Done. Ran `pytest tests/` — 47 passed, 0 failed, 2 skipped (the 2 skipped are pre-existing). Manually verified the new `/admin` route loads and renders the form.

NOT:

> Done. Should work.

The user can audit the first. The second is a guess wearing the costume of a result.

## Categories of verification

| Change type | Verification |
|---|---|
| Bug fix | Failing test now passes + full suite still passes |
| New feature | New tests cover it + manually exercise the feature + full suite passes |
| Refactor | Tests pass identically before and after |
| Performance | Benchmark numbers before and after, not just "feels faster" |
| Doc change | Read the rendered doc; check links |
| Config change | Run the thing the config affects; confirm behavior |

## Common failure modes

- **Type-check-as-success** — types pass, code is silently wrong, declared done
- **Cached green** — test suite shows old result; rerun before declaring
- **Selective verification** — ran the test you wrote but not the broader suite; the broader suite catches the regression you didn't think of
- **UI without UI verification** — built a UI feature, never opened a browser; type check is not feature verification
- **Verification by claim** — "this should pass"; should is not did
