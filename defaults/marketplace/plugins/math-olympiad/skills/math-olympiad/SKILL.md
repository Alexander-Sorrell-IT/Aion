---
name: math-olympiad
description: Solve competition math problems (IMO, Putnam, USAMO, AIME) with adversarial verification. Activates when asked to solve, prove, or verify any problem involving "IMO", "Putnam", "USAMO", "AIME", "olympiad", or "competition math". Uses pure reasoning, then a fresh-context verifier attacks the proof using specific failure patterns. Outputs calibrated confidence — will say "no confident solution" rather than bluff.
---

# math-olympiad

Competition math is the cleanest test of mathematical reasoning under adversarial conditions: the problem is stated precisely, the answer is verifiable, "almost right" is wrong.

## Why a separate verifier

Self-verification fails predictably: the part of you that wrote the proof has the same blind spot as the part of you checking it. The fix is to run verification in a fresh context that sees only the final proof — and instruct it to attack rather than confirm.

## Pipeline

1. **Solve.** Pure reasoning, no tools. Write the full proof. Flag any non-obvious step, invoked theorem, or case analysis.
2. **Compress to deliverable.** Strip your scratchpad. Produce the proof as it would appear in a writeup.
3. **Adversarial verify.** Dispatch a fresh-context subagent with only the problem and the proof. Instruct it to find a flaw — not "verify" generically (that produces rubber-stamps), but to look for specific failure patterns (below).
4. **Reconcile.** Verifier finds flaw → fix and re-verify. Verifier finds no flaw across two independent runs → ship the proof with confidence stated.
5. **Calibrate.** If after multiple rounds the proof has unresolved gaps, **say so**. "Partial argument; cannot close the n=2 case" beats a fake complete proof.

## Failure patterns the verifier checks

Generic "check the logic" misses these. Direct the verifier at:

- **Vacuous quantification** — "for all x in S, P(x)" — is S empty?
- **Strict vs non-strict drift** — did ≤ quietly become < at a step?
- **WLOG that isn't** — assumed symmetry that breaks the bounds
- **Hidden case split** — handled one branch, forgot the other
- **Induction base off-by-one** — works for n≥2 but claim is n≥1
- **Index bounds** — especially in summations and pigeonhole
- **Construction without verification** — exhibited an example, never proved it works
- **Bound vs equality** — showed x ≤ y, treated as x = y
- **Existence vs explicit** — claimed existence without exhibition where exhibition was required
- **Mod arithmetic drift** — working mod n, forgot which n

Verifier must quote the proof line for each check it applies.

## Output

- State confidence at the end: high / medium / low / no confident solution
- Never invent a confident proof when the verifier flagged something unresolved
- For value problems, the value goes on a single line at the top, separate from the proof
- Don't bury the answer in a paragraph

## When the verifier disagrees

The verifier has less context but fresher eyes. Default to taking the flag seriously: re-examine the questioned step, write it more carefully, re-run verification on the fix. Only override the verifier when you can write down explicitly why the flagged step is sound — and treat that as a yellow flag in your confidence.
