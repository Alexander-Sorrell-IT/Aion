---
name: executing-plans
description: Use when you have a written implementation plan to execute. Walks through the steps in order, runs verification after each, surfaces deviations, doesn't skip ahead.
---

# executing-plans

A plan is a contract. Execution means honoring it: doing the steps in order, verifying each, naming deviations explicitly when they happen.

## When to act

- You have a written plan (from `writing-plans` or provided by the user)
- The work is non-trivial and the plan was created to coordinate it

## When not to act

- You don't have a plan — write one first via `writing-plans`
- The plan is from before this session and the codebase has moved past it; refresh first

## The loop

For each step in order:

1. **Read the step.** Confirm you understand the change, the files, and the verification.
2. **Execute the change.** Edit only what the step names. If you find you need to touch a file the step doesn't mention, stop — either update the plan or surface the deviation to the user.
3. **Run the verification.** The one the step names. Not a substitute. If the step says "run pytest", run pytest, not "type check passes so probably good".
4. **Report.** One-line status: "Step N done — verification passed: <evidence>". Or if it failed, "Step N blocked — verification failed: <what failed, what you'll do>".

Move to the next step only after the current step's verification passes.

## Deviation handling

The plan won't survive contact with reality intact. When you hit a deviation:

- **Discovery deviation** (the codebase isn't what the plan assumed): stop. Report to the user. Either revise the plan or accept the deviation explicitly.
- **Scope deviation** (a step turns out to require work the plan didn't anticipate): stop. Don't silently expand scope. Either add the work as new steps or punt it.
- **Verification deviation** (the step's verification turns out to be insufficient): name what additional verification you ran and why.

Never silently expand a step's scope. The plan is a contract; breaking it without telling the user is the failure mode this skill prevents.

## Stop conditions

Stop and report (don't continue executing):

- Verification failure that the step doesn't tell you how to handle
- Discovery that an earlier step's outcome was wrong (you may need to revisit)
- A risk from the plan's "Risks" section materializing
- Anything destructive becomes necessary that the plan doesn't authorize

## Output cadence

Don't narrate every action. One line per step:

> Step 1 done — `npm test` passes (47 tests).
> Step 2 done — feature flag wired; `curl /api/x` returns 200 with the new shape.
> Step 3 blocked — migration fails on staging DB because column already exists. Need to amend the plan or skip the create-if-exists guard.

Walls of text per step waste the user's attention and bury the actual state.

## Common failure modes

- **Skipping verification** — moving to step 2 because step 1 "looked right"
- **Silent deviations** — taking on extra work or skipping a step without telling the user
- **Forgetting earlier steps** — by step 5, you no longer remember step 2's assumption; the plan is your memory
- **Over-narration** — three paragraphs per step instead of one line
- **Reading the plan once** — re-read each step right before executing it; the rest of the plan is context but the current step is the contract
