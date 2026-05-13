# doctor

Health-check the install. First-line diagnostic before debugging blind.

| Component | Triggered by |
|---|---|
| `doctor` agent | "doctor", "check my install", "diagnose", "something's wrong with the CLI" |
| `/doctor` command | Manual full sweep |

Checks 8 areas: config dir, settings.json, plugins, marketplaces, memory git, scripts, authentication, PATH. Reports issues in priority order with one-line fix suggestions. Never modifies anything without being asked.
