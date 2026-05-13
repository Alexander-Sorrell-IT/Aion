---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Produce a written plan that names files, steps, and verification — enough that another session could execute it.
---

# writing-plans

A plan is a contract: a written list of steps with named files and verification, such that someone else (or a future session) could execute it without you in the room. Plans force the design decisions to surface before code starts.

## When to act

- Task takes 3+ steps with dependencies
- Multiple files need changes that have to land together
- The work will span sessions and someone else might continue it
- The task touches risky areas (security, data migration, public APIs)

## When not to act

- Single-file edit with clear shape
- Exploratory work where the destination isn't yet known
- Tasks the user explicitly framed as "just try it"

## Plan format

```markdown
# <task title>

## Goal
One sentence: what's true after this is done that wasn't before.

## Out of scope
One bulleted list. What this plan does NOT do, that someone might assume it does.

## Steps

### 1. <imperative title>
- **Files:** `path/a.ts`, `path/b.ts`
- **Change:** what specifically changes
- **Verify:** how you know it worked (test, command, manual check)

### 2. ...

## Risks
What could go wrong, and how to catch it early.

## Verification (full)
After all steps: the combined check that proves the goal is met.
```

## Step discipline

- Each step is independently executable. You should be able to stop after step N, hand off, and the next person picks up from N+1.
- Each step has a verification. "Add a function" without "verify it's called" is incomplete.
- Steps name files. Don't say "update the auth layer" — say "edit `src/auth/middleware.ts`".

## Sizing

- Steps that take more than half a session of work should split.
- Plans with more than ~10 top-level steps should split into phases.
- A plan that's 3 lines is suspiciously light — usually missing the "out of scope" and "risks" sections.

## Before executing

After writing the plan, walk through it once asking:
- Is each step's verification *actually* sufficient to prove the step worked?
- Are there ordering dependencies between steps? Are they explicit?
- Is the "Out of scope" honest, or hiding work you'd be tempted to do?

If any answer is "no", revise before executing.

## Common failure modes

- **Plan as procrastination** — endless planning to avoid starting; plans serve execution, not the other way around
- **Steps without verification** — agent declares "done" on each step without checking; the plan can't catch this
- **Verification = "looks right"** — not actually verification
- **Plan diverges from execution silently** — when a step changes, edit the plan; otherwise the plan stops being a contract
- **Out-of-scope creep** — "while we're here" additions; either add explicit steps or skip them
