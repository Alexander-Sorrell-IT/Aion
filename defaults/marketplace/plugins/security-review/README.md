# security-review

Security audit of diffs and codebases. Signal-over-noise — every finding ships with a concrete exploit scenario.

| Component | Triggered by |
|---|---|
| `security-reviewer` agent | "security review", "is this safe", "OWASP audit" |
| `/audit` command | Audit current diff or specified scope |

Covers 10 vulnerability categories: hardcoded secrets, command/SQL injection, unsafe deserialization, auth bypass, path traversal, SSRF, log leakage, crypto mistakes, code-from-data. Severity-calibrated (CRITICAL → HIGH → MEDIUM → LOW); never pads with paranoia.
