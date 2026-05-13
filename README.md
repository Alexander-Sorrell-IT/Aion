# Aion

> Configurable agent CLI — any model, any brand, any toolkit.

Aion is an OSS command-line agent that runs against any LLM provider, ships with a plugin marketplace, and rebrands itself with one config edit. Bring your own model, your own toolkit, and (if you're shipping it commercially) your own name.

## Status

Alpha — `v0.1.0-alpha`. Agent core + brand-config build system done. Plugin loader, marketplace, memory-git, MCP, and installer in progress.

## Install (dev / editable)

```bash
git clone <repo-url> aion
cd aion
pip install -e .
```

You now have an `aion` command on PATH.

## Quick start

```bash
# Set your provider's API key
export OPENAI_API_KEY=sk-...

# One-shot
aion "what files are in this directory and how many lines of python total?"

# Interactive REPL
aion
```

## What's included today

| Component | Status |
|---|---|
| Agent loop (litellm-backed, multi-provider) | ✓ |
| Six tools: bash, read, write, edit, grep, glob | ✓ |
| Brand-config build system (rebrand to any name with one edit) | ✓ |
| Provider presets: openai, anthropic, deepseek, ollama, custom | ✓ |
| Plugin + marketplace loader | in progress |
| 13 bundled default plugins | in progress (copy-port from Proteus) |
| Memory-git (action-level audit trail) | planned |
| MCP integration | planned |
| Installer pipeline + permission UX | planned |

Pricing & commercial plans: details at aion.dev (coming with v1.0).

## Rebranding

Edit `brand.config.json`:

```json
{
  "binary":  "foo",
  "display": "foo",
  "configDir": "~/.foo",
  "api": { "preset": "deepseek" }
}
```

Then:

```bash
python scripts/build.py
pip install -e .
foo --version   # the binary is now `foo`, running against DeepSeek
```

Everything user-facing — binary name, config dir, default provider, default model — flows from `brand.config.json`. One edit rebrands the entire CLI.

## License

MIT for the agent core, base tools, and the bundled default plugins. See `LICENSE`.

Premium plugins and the commercial rebrand toolkit are distributed separately under a source-available commercial-use license. Details with v1.0.

## Project layout

```
aion/
├── src/aion/           # Python package
│   ├── agent.py        # LLM loop, tool dispatch, history
│   ├── tools.py        # bash, read, write, edit, grep, glob
│   ├── config.py       # brand.config.json loader
│   ├── cli.py          # Click entry, REPL, one-shot
│   └── __main__.py     # `python -m aion`
├── scripts/
│   ├── build.py        # Read brand.config.json, templatize pyproject.toml + .env-active
│   └── brand_presets.json   # openai / anthropic / deepseek / ollama / custom
├── defaults/
│   └── marketplace/    # Default plugin marketplace (populated by task 14)
├── brand.config.json   # The one file that controls everything
└── pyproject.toml      # Templated from brand.config.json on every build
```

## Roadmap

See in-progress tasks in the project tracker. Major milestones:

- **v0.2** — Plugin loader, marketplace, 13 default plugins ported
- **v0.3** — Memory-git, MCP, installer pipeline
- **v0.4** — Permission UX (status bar, presets, plan-accept dialog)
- **v1.0** — Public launch, pricing tiers live, documented plugin authoring
