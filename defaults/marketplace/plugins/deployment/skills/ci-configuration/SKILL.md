---
name: ci-configuration
description: Set up or improve continuous integration. Use when the user is configuring GitHub Actions / GitLab CI / Circle / Jenkins, asks "how should my CI be structured?", or has a CI pipeline that's slow, flaky, or missing checks.
---

# ci-configuration

CI exists to catch regressions before they reach main. A good CI pipeline is fast (under 10 min), deterministic, and tells you specifically what broke when it fails.

## When to act

- Setting up a new repo's CI
- User asks why their CI is slow / flaky / unhelpful
- Reviewing or proposing a CI config

## When not to act

- User wants to run tests locally (not CI)
- The project already has working CI and the user is just adding one new check

## What every CI pipeline needs

1. **Trigger** — when does it run? Push to main + PR opens/updates is the standard
2. **Setup** — checkout code, install deps, cache where possible
3. **Lint** — fast, catches stupid stuff. Run FIRST so failures are surfaced immediately.
4. **Type check** — also fast (if applicable). Catches whole classes of bugs.
5. **Unit tests** — bulk of the test value, should run in parallel if slow
6. **Integration tests** (optional) — if applicable, run after unit tests pass
7. **Build artifact** — if it doesn't build, none of the above means it ships

Each stage should fail fast: if lint fails, don't run tests.

## Speed wins

- **Cache dependencies** — every CI provider has a cache action. Use it. Cuts setup time by 70%.
- **Run lint + tests in parallel** — if independent, they shouldn't be sequential
- **Matrix only when needed** — testing on 5 Python versions × 3 OSes = 15 jobs. Be choosy.
- **Skip unchanged paths** — `paths:` filter on GitHub Actions to skip jobs when only docs changed
- **Self-hosted runners** for huge repos — but only if you can maintain them

## Reliability wins

- **Pin action versions** to a SHA, not `@v3` (which can move)
- **No `--retry-failures` flags** — they hide flaky tests. Fix the flakes.
- **Print enough on failure** — log files, screenshots, full stack traces. Don't make the user re-run with `--verbose`.
- **Deterministic test order** — avoid order-dependent tests (catch with `pytest --random-order`)
- **Time bounds** — every job should have a `timeout-minutes` so a hang doesn't burn 6 hours of compute

## Specific helpful checks

- **Block on red** — required-status-checks on main branch via repo settings
- **Auto-cancel stale runs** — when a PR gets a new push, cancel the previous run for the same PR
- **PR diff vs base** — for size limits, code coverage delta, security scans, run against the diff not the whole repo

## Common mistakes

- **`continue-on-error: true`** — turns failure into success silently. Almost never the right answer.
- **Secrets printed to logs** — make sure step outputs don't echo `${{ secrets.X }}`. Use `::add-mask::` if needed.
- **Build-and-deploy on every push to main** — fine for some projects, dangerous for others. Be explicit about what main triggers.
- **No PR draft handling** — PRs that are explicitly drafts shouldn't burn full CI. Add a filter.
- **`if: always()`** to ensure cleanup — fine, but combined with `continue-on-error` it can mask real failures.

## Output

For new CI setup, propose a minimal first pipeline. Then iterate. Don't ship a 200-line config when the user wanted to verify their tests run.
