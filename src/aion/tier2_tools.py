"""Tier 2 parity tools — second wave toward Proteus's 41-tool surface.

Tools in this module:
    notebook_edit   — manipulate Jupyter .ipynb cells (insert/replace/delete/move)
    enter_plan_mode — agent toggles plan_mode ON from inside its turn
    exit_plan_mode  — agent toggles plan_mode OFF (e.g. after the user approves)
    config_get      — read a value from the user's settings.json
    config_set      — write a value to the user's settings.json (gated)
    advisor         — consult a stronger reviewer model for second-opinion analysis

Registered by tools.py's _register_extras at import time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .tools import ToolResult


# ── notebook_edit ───────────────────────────────────────────────────────────


def _tool_notebook_edit(
    path: str,
    mode: str = "replace",
    cell_index: int = 0,
    cell_type: str = "code",
    source: str = "",
) -> ToolResult:
    """Edit a Jupyter notebook (.ipynb).

    Modes:
        replace  — replace cell at cell_index with new (source, cell_type)
        insert   — insert new cell BEFORE cell_index; index 0 = top, -1 = append
        delete   — remove cell at cell_index
        clear    — wipe outputs from all cells; leave source intact

    cell_type: 'code' | 'markdown' | 'raw' (only for insert/replace)
    """
    p = Path(path).expanduser()
    if not p.exists():
        return ToolResult(ok=False, content=f"notebook not found: {p}")
    if p.suffix != ".ipynb":
        return ToolResult(ok=False, content=f"not a .ipynb file: {p}")

    try:
        nb = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return ToolResult(ok=False, content=f"failed to read notebook: {e}")

    cells = nb.get("cells")
    if not isinstance(cells, list):
        return ToolResult(ok=False, content="notebook has no 'cells' array")

    if mode == "clear":
        wiped = 0
        for cell in cells:
            if cell.get("cell_type") == "code" and cell.get("outputs"):
                cell["outputs"] = []
                cell["execution_count"] = None
                wiped += 1
    elif mode == "delete":
        if not (0 <= cell_index < len(cells)):
            return ToolResult(ok=False, content=f"cell_index {cell_index} out of range (0..{len(cells)-1})")
        del cells[cell_index]
    elif mode in {"insert", "replace"}:
        if cell_type not in {"code", "markdown", "raw"}:
            return ToolResult(ok=False, content=f"cell_type must be code/markdown/raw")
        new_cell: dict[str, Any] = {
            "cell_type": cell_type,
            "metadata": {},
            "source": source.splitlines(keepends=True) if source else [],
        }
        if cell_type == "code":
            new_cell["outputs"] = []
            new_cell["execution_count"] = None

        if mode == "replace":
            if not (0 <= cell_index < len(cells)):
                return ToolResult(ok=False, content=f"cell_index {cell_index} out of range")
            cells[cell_index] = new_cell
        else:  # insert
            if cell_index < 0:
                cells.append(new_cell)
            else:
                cells.insert(cell_index, new_cell)
    else:
        return ToolResult(ok=False, content=f"unknown mode: {mode}")

    try:
        p.write_text(json.dumps(nb, indent=1) + "\n")
    except OSError as e:
        return ToolResult(ok=False, content=f"failed to write notebook: {e}")

    return ToolResult(
        ok=True,
        content=f"{mode} on {p} (cells: {len(cells)})",
        summary=f"{len(cells)} cells",
    )


_SCHEMA_NOTEBOOK_EDIT = {
    "type": "function",
    "function": {
        "name": "notebook_edit",
        "description": (
            "Edit a Jupyter notebook (.ipynb). Modes: replace (cell at index), "
            "insert (before index; -1 = append), delete (remove cell), clear "
            "(wipe all outputs)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path":       {"type": "string", "description": "Path to the .ipynb file."},
                "mode":       {"type": "string", "enum": ["replace", "insert", "delete", "clear"]},
                "cell_index": {"type": "integer", "description": "0-based cell index (-1 = append for insert)."},
                "cell_type":  {"type": "string", "enum": ["code", "markdown", "raw"]},
                "source":     {"type": "string", "description": "Cell source (for insert/replace)."},
            },
            "required": ["path", "mode"],
        },
    },
}


# ── enter_plan_mode / exit_plan_mode ────────────────────────────────────────


# Module-level reference to the agent's permission state. The CLI wires this
# at startup so the agent can flip the flag from inside its own turn.
_PERMISSION_STATE_REF: list = []  # mutable container


def set_permission_state(state) -> None:
    _PERMISSION_STATE_REF.clear()
    _PERMISSION_STATE_REF.append(state)


def _tool_enter_plan_mode(reason: str = "") -> ToolResult:
    """Agent calls this to signal it's now in plan mode — it will WRITE a plan
    instead of executing. The plan goes to the user as text; the user approves
    (or redirects), then the agent calls exit_plan_mode to resume normal mode.
    """
    if not _PERMISSION_STATE_REF:
        return ToolResult(
            ok=False,
            content="plan mode unavailable (permission state not wired)",
        )
    state = _PERMISSION_STATE_REF[0]
    state.plan_mode = True
    msg = "entering plan mode — write the plan, do not execute"
    if reason:
        msg += f" ({reason})"
    return ToolResult(ok=True, content=msg)


_SCHEMA_ENTER_PLAN_MODE = {
    "type": "function",
    "function": {
        "name": "enter_plan_mode",
        "description": (
            "Switch yourself into plan mode. Use when the task is risky or "
            "non-trivial enough that you should write a plan first before "
            "executing. After calling this, produce the plan as text and wait "
            "for user approval; then call exit_plan_mode to resume."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why plan mode (one sentence)."},
            },
        },
    },
}


def _tool_exit_plan_mode(approved: bool = True) -> ToolResult:
    """Agent calls this after the user has approved (or rejected) the plan.
    Flips plan_mode back to False; if approved=False the agent should not
    execute the plan but instead surface that to the user."""
    if not _PERMISSION_STATE_REF:
        return ToolResult(
            ok=False,
            content="plan mode unavailable (permission state not wired)",
        )
    state = _PERMISSION_STATE_REF[0]
    state.plan_mode = False
    if approved:
        return ToolResult(ok=True, content="exiting plan mode — proceeding with execution")
    return ToolResult(ok=True, content="exiting plan mode — plan not approved; stopping")


_SCHEMA_EXIT_PLAN_MODE = {
    "type": "function",
    "function": {
        "name": "exit_plan_mode",
        "description": (
            "Exit plan mode after the user has reviewed your plan. Pass "
            "approved=true if they accepted, false if they rejected."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean", "default": True},
            },
        },
    },
}


# ── config_get / config_set ─────────────────────────────────────────────────


def _settings_path() -> Path:
    """Resolve the user's settings.json path. Reads CLAUDE_CONFIG_DIR /
    AION_CONFIG_DIR / falls back to ~/.aion."""
    for env_name in ("AION_CONFIG_DIR", "CLAUDE_CONFIG_DIR"):
        if env_name in os.environ:
            return Path(os.environ[env_name]).expanduser() / "settings.json"
    return Path.home() / ".aion" / "settings.json"


def _load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _save_settings(data: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _tool_config_get(key: str = "") -> ToolResult:
    """Read a value from the user's settings.json. Empty key returns the
    whole document. Dotted keys (e.g. 'enabledPlugins.foo') drill in."""
    settings = _load_settings()
    if not key:
        return ToolResult(
            ok=True,
            content=json.dumps(settings, indent=2),
            summary=f"{len(settings)} top-level keys",
        )
    parts = key.split(".")
    cur: Any = settings
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ToolResult(ok=False, content=f"key not found: {key}")
    if isinstance(cur, (dict, list)):
        return ToolResult(ok=True, content=json.dumps(cur, indent=2))
    return ToolResult(ok=True, content=str(cur))


_SCHEMA_CONFIG_GET = {
    "type": "function",
    "function": {
        "name": "config_get",
        "description": "Read a value from the user's settings.json. Empty key returns the whole document. Use dotted keys to drill into nested objects.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Dotted key path, or empty for the full doc."},
            },
        },
    },
}


def _tool_config_set(key: str, value: str) -> ToolResult:
    """Write a value to the user's settings.json at the given dotted key path.
    Value is parsed as JSON if it looks like JSON (true/false/null/numbers/
    objects/arrays); otherwise stored as a string."""
    if not key:
        return ToolResult(ok=False, content="key is required")

    # Try parsing value as JSON; fall back to string
    try:
        parsed: Any = json.loads(value)
    except json.JSONDecodeError:
        parsed = value

    settings = _load_settings()
    parts = key.split(".")
    cur = settings
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = parsed

    _save_settings(settings)
    return ToolResult(
        ok=True,
        content=f"set {key} = {json.dumps(parsed)[:100]}",
        summary=key,
    )


_SCHEMA_CONFIG_SET = {
    "type": "function",
    "function": {
        "name": "config_set",
        "description": "Write a value to the user's settings.json. Use dotted keys for nested paths. Value is parsed as JSON if it looks like JSON, otherwise stored as a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "key":   {"type": "string", "description": "Dotted key path."},
                "value": {"type": "string", "description": "Value to write (JSON-parseable or raw string)."},
            },
            "required": ["key", "value"],
        },
    },
}


# ── advisor ─────────────────────────────────────────────────────────────────


def _tool_advisor(question: str, context: str = "") -> ToolResult:
    """Consult a stronger reviewer model for a second opinion.

    The advisor is a separate LLM call, configured via:
        AION_ADVISOR_MODEL  — model identifier (e.g. 'gpt-4o', 'claude-opus-4-7')
        AION_ADVISOR_PROMPT — optional system-prompt prefix for the advisor

    Returns the advisor's response text. The agent can then choose to take the
    advice or not — it's advisory, not authoritative.
    """
    if not question.strip():
        return ToolResult(ok=False, content="question is required")

    advisor_model = os.environ.get("AION_ADVISOR_MODEL") or os.environ.get("AION_MODEL")
    if not advisor_model:
        return ToolResult(
            ok=False,
            content="no advisor model configured (set AION_ADVISOR_MODEL or AION_MODEL)",
        )

    advisor_system = os.environ.get(
        "AION_ADVISOR_PROMPT",
        "You are a senior reviewer being consulted by a junior agent. "
        "Give a direct, calibrated second opinion. Be specific. Identify what "
        "the junior may be missing. If they're right, say so concisely; if "
        "they're wrong, say what's wrong and how to think about it instead.",
    )

    user_msg = question
    if context:
        user_msg = f"Context the junior agent has:\n{context}\n\nQuestion: {question}"

    try:
        from litellm import completion  # type: ignore[import-not-found]
        response = completion(
            model=advisor_model,
            messages=[
                {"role": "system", "content": advisor_system},
                {"role": "user", "content": user_msg},
            ],
            stream=False,  # ensure we get a single ModelResponse, not a StreamWrapper
        )
        # response is a ModelResponse here; .choices is well-defined.
        text = response.choices[0].message.content or ""  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, content=f"advisor call failed: {e}")

    return ToolResult(
        ok=True,
        content=text,
        summary=f"advisor: {advisor_model}",
    )


_SCHEMA_ADVISOR = {
    "type": "function",
    "function": {
        "name": "advisor",
        "description": (
            "Consult a stronger reviewer model for a second opinion. Use when "
            "stuck, when a decision is high-stakes, or before declaring a task "
            "complete. Pass the question and any relevant context. Returns the "
            "advisor's response — advisory, not authoritative."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "What you're asking the advisor."},
                "context":  {"type": "string", "description": "Optional: relevant context the advisor needs."},
            },
            "required": ["question"],
        },
    },
}


# ── registry ────────────────────────────────────────────────────────────────


TIER2_TOOL_REGISTRY: dict[str, Any] = {
    "notebook_edit":   _tool_notebook_edit,
    "enter_plan_mode": _tool_enter_plan_mode,
    "exit_plan_mode":  _tool_exit_plan_mode,
    "config_get":      _tool_config_get,
    "config_set":      _tool_config_set,
    "advisor":         _tool_advisor,
}

TIER2_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _SCHEMA_NOTEBOOK_EDIT,
    _SCHEMA_ENTER_PLAN_MODE,
    _SCHEMA_EXIT_PLAN_MODE,
    _SCHEMA_CONFIG_GET,
    _SCHEMA_CONFIG_SET,
    _SCHEMA_ADVISOR,
]
