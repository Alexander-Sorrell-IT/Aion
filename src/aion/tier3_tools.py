"""Tier 3 tools — the long tail.

The tools here are useful but specialized. Most are simple wrappers around
existing capability rather than new logic, so they cost little but cover
the niche cases Proteus's audience may need.

Tools provided:
    sleep           — pause N seconds (useful in scripted runs)
    enter_worktree  — create + cd into a git worktree
    exit_worktree   — leave the worktree (cd back)
    brief           — summarize a long block of text via an LLM call
    skill_invoke    — explicitly load and run a skill body in the agent's context
    tool_search     — search the agent's own registered tools by name/description
    schedule_at     — schedule a one-off prompt for later (background thread)
    read_mcp_resource — fetch a resource by URI from an MCP server
    list_mcp_resources — enumerate resources offered by an MCP server

Skipped from Proteus (won't port):
    PowerShellTool       — Windows-only; bash covers it on the dominant platforms
    REPLTool             — Python eval is risky; use bash with python -c instead
    LSPTool              — heavyweight; needs full language-server protocol
    TeamCreate/Delete    — multi-tenant feature for the SaaS layer, not the CLI
    SendMessage/Remote/Trigger — multi-agent comms; future feature
    SyntheticOutputTool  — internal Anthropic testing tool
    McpAuthTool          — OAuth flow wrapper; specific to managed marketplaces

If users actually demand any of these, build them later. Not blocking v1.0.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .tools import ToolResult


# ── sleep ────────────────────────────────────────────────────────────────────


def _tool_sleep(seconds: float) -> ToolResult:
    """Pause for a number of seconds. Capped at 60s so the agent can't
    accidentally hang for an hour."""
    if seconds <= 0:
        return ToolResult(ok=False, content="seconds must be positive")
    seconds = min(seconds, 60.0)
    time.sleep(seconds)
    return ToolResult(ok=True, content=f"slept {seconds}s")


_SCHEMA_SLEEP = {
    "type": "function",
    "function": {
        "name": "sleep",
        "description": "Pause execution for N seconds (capped at 60). Use for polling external state.",
        "parameters": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
    },
}


# ── enter_worktree / exit_worktree ──────────────────────────────────────────


# Track the original cwd so exit_worktree can return there.
_WORKTREE_STACK: list[Path] = []


def _tool_enter_worktree(branch: str, path: str = "") -> ToolResult:
    """Create a git worktree on `branch` at `path` (default: ../<repo>-<branch>)
    and chdir there. Use to isolate work from the main checkout.

    Returns the worktree path. exit_worktree returns to the previous dir.
    """
    if not branch.strip():
        return ToolResult(ok=False, content="branch is required")

    # Confirm we're in a git repo
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return ToolResult(ok=False, content="not in a git repository")
    repo_root = Path(proc.stdout.strip())

    if not path:
        path = str(repo_root.parent / f"{repo_root.name}-{re.sub(r'[^a-zA-Z0-9_-]', '-', branch)}")

    target = Path(path).expanduser().resolve()

    # Create the worktree. -B creates branch if missing.
    proc = subprocess.run(
        ["git", "worktree", "add", "-B", branch, str(target)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return ToolResult(
            ok=False,
            content=f"git worktree add failed: {proc.stderr.strip()}",
        )

    _WORKTREE_STACK.append(Path.cwd())
    os.chdir(target)
    return ToolResult(
        ok=True,
        content=f"created worktree at {target} on branch '{branch}'; cwd switched",
        summary=str(target),
    )


_SCHEMA_ENTER_WORKTREE = {
    "type": "function",
    "function": {
        "name": "enter_worktree",
        "description": "Create a git worktree on the given branch and chdir into it. Isolates work from the main checkout.",
        "parameters": {
            "type": "object",
            "properties": {
                "branch": {"type": "string"},
                "path": {"type": "string", "description": "Optional; defaults to ../<repo>-<branch>"},
            },
            "required": ["branch"],
        },
    },
}


def _tool_exit_worktree(remove: bool = False) -> ToolResult:
    """Leave the current worktree (cd back). If remove=True, also `git worktree
    remove` the directory."""
    if not _WORKTREE_STACK:
        return ToolResult(ok=False, content="not inside an enter_worktree session")

    current = Path.cwd()
    prior = _WORKTREE_STACK.pop()
    os.chdir(prior)

    msg = f"left worktree {current}, returned to {prior}"
    if remove:
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(current)],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            msg += "; worktree removed"
        else:
            msg += f"; remove failed: {proc.stderr.strip()}"
    return ToolResult(ok=True, content=msg)


_SCHEMA_EXIT_WORKTREE = {
    "type": "function",
    "function": {
        "name": "exit_worktree",
        "description": "Leave the current worktree (cd back). remove=True also deletes the worktree dir.",
        "parameters": {
            "type": "object",
            "properties": {"remove": {"type": "boolean", "default": False}},
        },
    },
}


# ── brief (summarize) ────────────────────────────────────────────────────────


def _tool_brief(text: str, instruction: str = "Summarize concisely.") -> ToolResult:
    """Summarize a long text via the same LLM the agent uses. Useful when the
    agent has a large chunk of content (e.g. log output) it wants to reference
    later without keeping the full text in context."""
    if not text.strip():
        return ToolResult(ok=False, content="text is required")

    model = os.environ.get("AION_MODEL", "gpt-4o-mini")
    try:
        from litellm import completion  # type: ignore[import-not-found]
        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": "You produce concise, faithful summaries."},
                {"role": "user", "content": f"{instruction}\n\n---\n\n{text}"},
            ],
            stream=False,
        )
        summary = response.choices[0].message.content or ""  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, content=f"brief call failed: {e}")
    return ToolResult(ok=True, content=summary, summary=f"{len(summary)} chars from {len(text)}")


_SCHEMA_BRIEF = {
    "type": "function",
    "function": {
        "name": "brief",
        "description": "Summarize a long text via an LLM call. Use to compress large chunks (logs, docs) before putting them in your working context.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "instruction": {"type": "string", "description": "How to summarize (default: concise summary)."},
            },
            "required": ["text"],
        },
    },
}


# ── skill_invoke ────────────────────────────────────────────────────────────


# The CLI stores active skills in a module-level reference so this tool can
# find them. Wired in cli.py's _build_agent.
_SKILLS_REF: list = []


def set_skills_ref(skills) -> None:
    _SKILLS_REF.clear()
    _SKILLS_REF.append(skills)


def _tool_skill_invoke(name: str) -> ToolResult:
    """Explicitly load a skill's body into the agent's context.

    Normally the agent decides whether to use a skill based on the description
    advertised in the system prompt. This tool lets the agent (or the user
    via /skill <name>) load the full body on demand."""
    if not _SKILLS_REF:
        return ToolResult(ok=False, content="no active skills (skills not wired)")
    skills = _SKILLS_REF[0]
    for skill in skills:
        if skill.name == name:
            return ToolResult(
                ok=True,
                content=f"# Skill: {skill.name}\n\n{skill.body}",
                summary=f"loaded skill '{name}' ({len(skill.body)} chars)",
            )
    available = ", ".join(s.name for s in skills) or "(none)"
    return ToolResult(ok=False, content=f"skill '{name}' not found. Available: {available}")


_SCHEMA_SKILL_INVOKE = {
    "type": "function",
    "function": {
        "name": "skill_invoke",
        "description": "Load a skill's body text into your context. Use when you decided based on the skill's description in the system prompt that you want to consult its full content.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The skill name."}},
            "required": ["name"],
        },
    },
}


# ── tool_search ─────────────────────────────────────────────────────────────


def _tool_tool_search(query: str) -> ToolResult:
    """Search the registered tools by name + description. Returns matching tools."""
    from .tools import TOOL_SCHEMAS  # lazy to avoid circular at module load

    q = query.lower()
    matches = []
    for schema in TOOL_SCHEMAS:
        fn = schema.get("function", {})
        name = fn.get("name", "")
        desc = fn.get("description", "")
        if q in name.lower() or q in desc.lower():
            matches.append((name, desc))
    if not matches:
        return ToolResult(ok=True, content="(no matches)", summary="0")
    lines = [f"- **{n}** — {d.splitlines()[0] if d else ''}" for n, d in matches]
    return ToolResult(ok=True, content="\n".join(lines), summary=f"{len(matches)} matches")


_SCHEMA_TOOL_SEARCH = {
    "type": "function",
    "function": {
        "name": "tool_search",
        "description": "Search your own registered tools by query string. Useful when you're not sure which tool name corresponds to a capability.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


# ── schedule_at ─────────────────────────────────────────────────────────────


# Module-level scheduled tasks. In-memory only; not persisted across restart.
_SCHEDULED_TASKS: list[dict[str, Any]] = []


def _run_scheduled(task_id: str, delay: float, prompt: str) -> None:
    time.sleep(delay)
    # Lazy import to avoid circular dep
    try:
        from .agent import Agent
        from .config import load_brand_config
        for parent in [Path.cwd(), *Path.cwd().parents]:
            if (parent / "brand.config.json").exists():
                brand = load_brand_config(parent)
                agent = Agent(brand=brand)
                result = agent.execute(prompt)
                for t in _SCHEDULED_TASKS:
                    if t["id"] == task_id:
                        t["status"] = "completed"
                        t["result"] = result
                        t["completed_at"] = time.time()
                        break
                return
    except Exception as e:  # noqa: BLE001
        for t in _SCHEDULED_TASKS:
            if t["id"] == task_id:
                t["status"] = "failed"
                t["error"] = str(e)
                break


def _tool_schedule_at(delay_seconds: float, prompt: str, description: str = "") -> ToolResult:
    """Schedule a prompt to run later. Returns immediately; the agent runs in
    a background thread after delay_seconds. Capped at 1 hour delay."""
    import uuid
    if delay_seconds < 0:
        return ToolResult(ok=False, content="delay_seconds must be non-negative")
    delay_seconds = min(delay_seconds, 3600.0)

    task_id = f"sched_{uuid.uuid4().hex[:8]}"
    _SCHEDULED_TASKS.append({
        "id": task_id,
        "description": description or prompt[:60],
        "delay_seconds": delay_seconds,
        "fires_at": time.time() + delay_seconds,
        "status": "scheduled",
    })

    thread = threading.Thread(
        target=_run_scheduled,
        args=(task_id, delay_seconds, prompt),
        daemon=True,
        name=f"aion-sched-{task_id}",
    )
    thread.start()
    return ToolResult(
        ok=True,
        content=f"scheduled {task_id} to fire in {delay_seconds:.0f}s",
        summary=task_id,
    )


_SCHEMA_SCHEDULE_AT = {
    "type": "function",
    "function": {
        "name": "schedule_at",
        "description": "Schedule a prompt to run in a fresh agent after N seconds (capped 1 hour). Background; returns immediately.",
        "parameters": {
            "type": "object",
            "properties": {
                "delay_seconds": {"type": "number"},
                "prompt": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["delay_seconds", "prompt"],
        },
    },
}


# ── MCP resource tools ──────────────────────────────────────────────────────


# Reference to the MCPManager, wired by the CLI at startup.
_MCP_REF: list = []


def set_mcp_manager(mcp_manager) -> None:
    _MCP_REF.clear()
    if mcp_manager:
        _MCP_REF.append(mcp_manager)


def _tool_list_mcp_resources(server_name: str = "") -> ToolResult:
    """List resources offered by MCP servers. Empty server_name lists across all."""
    if not _MCP_REF:
        return ToolResult(ok=True, content="(no MCP servers configured)", summary="0")
    mgr = _MCP_REF[0]
    lines = []
    for name, server in mgr.servers.items():
        if server_name and name != server_name:
            continue
        try:
            result = server._send_request("resources/list")
            for r in result.get("resources", []):
                lines.append(f"- {name}: {r.get('uri', '?')}  — {r.get('description', '')}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"- {name}: ERROR — {e}")
    if not lines:
        return ToolResult(ok=True, content="(no resources)", summary="0")
    return ToolResult(ok=True, content="\n".join(lines), summary=f"{len(lines)} resources")


_SCHEMA_LIST_MCP_RESOURCES = {
    "type": "function",
    "function": {
        "name": "list_mcp_resources",
        "description": "List resources from MCP servers. Empty server_name lists across all configured servers.",
        "parameters": {
            "type": "object",
            "properties": {"server_name": {"type": "string"}},
        },
    },
}


def _tool_read_mcp_resource(uri: str, server_name: str = "") -> ToolResult:
    """Read a resource by URI from an MCP server. Empty server_name tries each
    until one succeeds."""
    if not _MCP_REF:
        return ToolResult(ok=False, content="no MCP servers configured")
    mgr = _MCP_REF[0]

    tried = []
    for name, server in mgr.servers.items():
        if server_name and name != server_name:
            continue
        try:
            result = server._send_request("resources/read", {"uri": uri})
            contents = result.get("contents", [])
            text_parts = [
                c.get("text", "") for c in contents
                if isinstance(c, dict) and c.get("type") in {"text", None}
            ]
            return ToolResult(
                ok=True,
                content="\n".join(text_parts) or "(empty)",
                summary=f"from {name}",
            )
        except Exception as e:  # noqa: BLE001
            tried.append(f"{name}: {e}")
    return ToolResult(
        ok=False,
        content=f"resource '{uri}' not readable. Tried: {'; '.join(tried) or '(no servers tried)'}",
    )


_SCHEMA_READ_MCP_RESOURCE = {
    "type": "function",
    "function": {
        "name": "read_mcp_resource",
        "description": "Read a resource by URI from an MCP server. Empty server_name tries each configured server until one succeeds.",
        "parameters": {
            "type": "object",
            "properties": {
                "uri": {"type": "string"},
                "server_name": {"type": "string"},
            },
            "required": ["uri"],
        },
    },
}


# ── registry ────────────────────────────────────────────────────────────────


TIER3_TOOL_REGISTRY: dict[str, Any] = {
    "sleep":              _tool_sleep,
    "enter_worktree":     _tool_enter_worktree,
    "exit_worktree":      _tool_exit_worktree,
    "brief":              _tool_brief,
    "skill_invoke":       _tool_skill_invoke,
    "tool_search":        _tool_tool_search,
    "schedule_at":        _tool_schedule_at,
    "list_mcp_resources": _tool_list_mcp_resources,
    "read_mcp_resource":  _tool_read_mcp_resource,
}

TIER3_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _SCHEMA_SLEEP,
    _SCHEMA_ENTER_WORKTREE,
    _SCHEMA_EXIT_WORKTREE,
    _SCHEMA_BRIEF,
    _SCHEMA_SKILL_INVOKE,
    _SCHEMA_TOOL_SEARCH,
    _SCHEMA_SCHEDULE_AT,
    _SCHEMA_LIST_MCP_RESOURCES,
    _SCHEMA_READ_MCP_RESOURCE,
]
