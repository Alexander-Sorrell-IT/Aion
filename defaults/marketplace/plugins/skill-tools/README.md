# skill-tools

Tools for building, reviewing, and benchmarking skills.

| Component | Triggered by |
|---|---|
| `skill-creator` skill | "create a skill", "make a skill for X", "improve this skill" |
| `skill-reviewer` agent | "review my skill", "check skill quality" |
| `skill-grader` agent | "benchmark this skill", "test triggering accuracy" |

The skill-creator skill handles the writing. The skill-reviewer agent audits an existing skill against best practices. The skill-grader agent scores triggering accuracy empirically against a set of test prompts.
