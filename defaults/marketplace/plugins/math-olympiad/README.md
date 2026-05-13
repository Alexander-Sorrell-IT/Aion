# math-olympiad

Solve IMO / Putnam / USAMO / AIME problems with adversarial verification.

The solver and the verifier are different passes — same model, fresh context for the verifier — because the part of you that wrote the proof has the same blind spot as the part of you checking it. The verifier attacks the proof against a checklist of specific competition-math failure modes (vacuous quantification, strict-vs-non-strict drift, off-by-one induction bases, etc.), not generic "look it over".

When the verifier still has questions after multiple rounds, the skill declines instead of bluffing.
