---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code. Write a failing test first, then make it pass, then refactor. Activates on "add a feature", "fix this bug", "implement X".
---

# test-driven-development

TDD isn't a religion. It's a forcing function: writing the test first proves you can describe the behavior you want; making it pass proves you delivered exactly that and nothing more.

## The loop

1. **Red.** Write a test that describes the behavior you want. Run it. Confirm it fails. If it passes, the behavior already exists — you didn't have a task.
2. **Green.** Write the smallest implementation that makes the test pass. Not the right implementation — the simplest. Resist the urge to design.
3. **Refactor.** Now that the test pins the behavior, rearrange the implementation without changing what it does. Run the test after each change. If it goes red, you broke something.

Loop until the feature is done.

## When to act

- Any task with verifiable behavior: feature, bug fix, refactor that should preserve behavior
- Any code change in a codebase with a test suite

## When not to act

- Exploratory spike work where you don't yet know what to test
- Trivial mechanical changes (rename, format, dependency bump)
- Code with no testability (and no path to making it testable)

## The discipline

The hardest part of TDD is not skipping red. The temptation is to write the implementation first and then add a test that "verifies" it — but a test you wrote after the code can't tell you anything about the code; it can only confirm what's there.

Write the test first. Run it. Watch it fail. *Then* implement. This is non-negotiable for the skill to do its work.

## Test selection

- Test behavior, not implementation. "User can log in" vs "calls authMiddleware with token".
- Cover the boundary: happy path, edge, error, empty.
- One assertion per test where possible — failures should localize.
- Names describe the behavior: `test_user_can_log_in_with_valid_credentials` not `test_login_1`.

## When the test is hard to write

The code is probably hard to test for structural reasons. Common causes:

- **Hidden dependencies** — code depends on globals, env, or singletons. Refactor to inject.
- **Side-effect tangling** — code does five things in one function. Split.
- **No seam** — there's no point in the code where you can substitute a fake. Add one.

A hard-to-test piece of code is a signal — not an excuse to skip the test.

## Refactor pass

After green, look at:
- Names that don't match what the code does anymore
- Duplication introduced by the smallest-implementation step
- Comments that have rotted (or were never useful)
- Anything you can delete without breaking the test

Run the test after each change. Tests stay green; code gets cleaner.

## Common failure modes

- **Skipping red** — writing test after implementation; defeats the point
- **Over-implementing in green** — adding speculative code "while you're there"
- **Refactor changing behavior** — silently expanding scope; the test should catch this but only if you actually run it
- **Test bloat** — testing every internal function instead of the behavior; lots of tests, none of them load-bearing
