---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes. Pin the failure, find the root cause, verify the fix actually fixes it.
---

# systematic-debugging

The default failure mode of debugging is to guess at causes and try changes. This skill forces a discipline: reproduce, isolate, understand, fix, verify.

## When to act

- A test failed unexpectedly
- A feature stopped working
- A user reports something is broken
- You see a stack trace or unexpected output

## When not to act

- The cause is obvious (you just made a typo, the linter says so) — fix it
- The user already diagnosed it correctly and is asking you to apply the fix

## The pipeline

### 1. Pin the failure

- What's the exact failure? Not "it's broken" — the error message, the failing assertion, the wrong output.
- Reproduce it. If you can't reproduce, you can't fix — you can only paper over.
- Minimize the repro. The smallest input that triggers the bug is also the easiest to reason about.

### 2. Find the boundary

The bug lives between code that works and code that doesn't. Find the boundary:
- What's the most recent change? (`git log`, `git bisect`)
- What's the input that crosses from working to broken?
- Which subsystem starts producing wrong output?

Don't read all the code looking for the bug. Bisect.

### 3. Understand the cause

Once you find the broken code, ask:
- Why does it produce this wrong result?
- Was the code wrong, the input wrong, or the assumption wrong?
- Is this a single bug or a class of bugs (e.g., all callers of this function are similarly broken)?

A fix that doesn't answer "why" is a guess. Guesses produce regressions.

### 4. Fix

The fix should be the minimal change that addresses the root cause. Resist:
- Adding error handling that swallows the bug
- Refactoring "while you're here"
- Generalizing the fix to cases you haven't proven are broken

### 5. Verify

- Run the failing test. It should pass.
- Run the full suite. Nothing else should break.
- Re-run the original reproduction. The bug should be gone.

If any of these fails, you haven't fixed it. You've moved it.

## When the bug doesn't reproduce

If you can't reproduce, you can't be sure you fixed anything. Options:
- **Add logging or instrumentation** — make the bug surface its state
- **Time-bound** — agree with the user on a deadline; after that, ship the most likely fix with monitoring
- **Hypothesize and falsify** — list plausible causes, design experiments that distinguish them

Never claim to have fixed a bug you couldn't reproduce.

## Common failure modes

- **Treating symptoms** — adding null checks instead of finding why null appeared
- **Pattern-matching fix to wrong cause** — "I've seen this stack trace before" without verifying the actual cause is the same
- **Fix-by-shotgun** — changing five things and seeing what works; you won't know which was the real fix
- **Skipping verification** — declaring done because the test you ran passed, without confirming the original bug is gone
- **Premature generalization** — fixing the one case, then "fixing" four other places by analogy without proving they were broken the same way
