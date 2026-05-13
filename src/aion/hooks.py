"""Hook engine — lifecycle event dispatch.

Hooks are user-configurable actions that fire at lifecycle events:
    PreToolUse        — before a tool is invoked
    PostToolUse       — after a tool returns
    SessionStart      — when the agent starts
    SessionEnd        — when the agent exits
    UserPromptSubmit  — when the user sends a prompt

Each hook entry has a matcher (regex against the tool name, or a literal
event-phase like "startup") and one or more commands. We support two
command kinds:

    {"type": "command", "command": "<shell command>"}
        Runs the shell command. Stdout becomes additional context for the
        agent (for PreToolUse / UserPromptSubmit hooks).

    {"type": "prompt", "prompt": "<text>"}
        Adds the text directly to the agent's context. Useful for guidance
        the user wants the agent to consider at the moment of the event.

Built-in hooks always installed by aion:
    PostToolUse(Write|Edit|MultiEdit) → memory_git.autocommit()
    SessionEnd                        → memory_git.autopush() if autoPush=true

Plus any hooks the user has configured in <config>/settings.json `hooks`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import BrandConfig
from .memory_git import autocommit as _mg_autocommit
from .memory_git import autopush as _mg_autopush


@dataclass
class HookEvent:
    """One firing of one event. Passed to hook handlers as context."""
    phase: str  # "PreToolUse" / "PostToolUse" / "SessionStart" / "SessionEnd" / "UserPromptSubmit"
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result_ok: bool | None = None
    user_prompt: str | None = None


def _load_user_hooks(config_dir: Path) -> dict[str, list[dict]]:
    """Read hooks block from <config>/settings.json. Returns {event: [matchers...]}."""
    settings_path = config_dir / "settings.json"
    if not settings_path.exists():
        return {}
    try:
        data = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {}
    return data.get("hooks", {}) or {}


def _matcher_matches(matcher: str | None, event: HookEvent) -> bool:
    """Does the configured matcher match this event?

    For tool-use events: matcher is a regex against the tool name.
    For lifecycle events: matcher is the phase name (or empty / wildcard).
    """
    if not matcher:
        return True
    if event.phase in {"PreToolUse", "PostToolUse"} and event.tool_name:
        try:
            return bool(re.match(matcher, event.tool_name))
        except re.error:
            return False
    if event.phase == "SessionStart":
        return matcher in {"startup", "*", ""}
    return matcher in {"*", ""}


def _run_command_hook(command: str, env: dict[str, str] | None = None) -> tuple[int, str]:
    """Execute a shell command hook. Returns (exit_code, stdout)."""
    # Build the env dict explicitly so the type checker can see it's a plain
    # dict[str, str] and not the os._Environ wrapper.
    merged_env: dict[str, str] | None = None
    if env is not None:
        merged_env = dict(os.environ)
        merged_env.update(env)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=30,
            env=merged_env,
        )
        return proc.returncode, proc.stdout
    except subprocess.TimeoutExpired:
        return 1, ""
    except Exception:
        return 1, ""


class HookEngine:
    """Routes lifecycle events to:
       1. Built-in handlers (memory-git autocommit / autopush)
       2. User-configured hooks from settings.json
    """

    def __init__(self, brand: BrandConfig, config_dir: Path) -> None:
        self.brand = brand
        self.config_dir = config_dir
        self._memory_dir = config_dir / "memory"
        self._user_hooks = _load_user_hooks(config_dir)
        # Snapshot the brand flags so the hook commands don't have to re-load
        self._autocommit = brand.memory_git.auto_commit
        self._autopush = brand.memory_git.auto_push

    # ── built-in handlers ────────────────────────────────────────────────────

    def _builtin_post_tool(self, event: HookEvent) -> None:
        """After Write/Edit/MultiEdit, autocommit the memory dir if enabled."""
        if not self._autocommit:
            return
        if event.tool_name not in {"write", "edit", "multiedit"}:
            return
        _mg_autocommit(self._memory_dir)

    def _builtin_session_end(self) -> None:
        """On session end, push memory if autoPush is on AND a remote exists."""
        if self._autopush:
            _mg_autopush(self._memory_dir)

    # ── user-hook dispatch ───────────────────────────────────────────────────

    def _dispatch_user_hooks(self, event: HookEvent) -> list[str]:
        """Run user-configured hooks for this event. Collects any prompt-style
        contributions to return to the caller (which feeds them back into the
        agent's context)."""
        added_context: list[str] = []
        for entry in self._user_hooks.get(event.phase, []):
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher")
            if not _matcher_matches(matcher, event):
                continue
            for hook in entry.get("hooks", []):
                kind = hook.get("type")
                if kind == "command":
                    _run_command_hook(hook.get("command", ""))
                elif kind == "prompt":
                    text = hook.get("prompt", "")
                    if text:
                        added_context.append(text)
        return added_context

    # ── public events ───────────────────────────────────────────────────────

    def post_tool_use(self, tool_name: str, tool_args: dict, ok: bool) -> list[str]:
        event = HookEvent(
            phase="PostToolUse",
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result_ok=ok,
        )
        self._builtin_post_tool(event)
        return self._dispatch_user_hooks(event)

    def pre_tool_use(self, tool_name: str, tool_args: dict) -> list[str]:
        event = HookEvent(phase="PreToolUse", tool_name=tool_name, tool_args=tool_args)
        return self._dispatch_user_hooks(event)

    def session_start(self) -> list[str]:
        event = HookEvent(phase="SessionStart")
        return self._dispatch_user_hooks(event)

    def session_end(self) -> list[str]:
        event = HookEvent(phase="SessionEnd")
        self._builtin_session_end()
        return self._dispatch_user_hooks(event)

    def user_prompt_submit(self, user_text: str) -> list[str]:
        event = HookEvent(phase="UserPromptSubmit", user_prompt=user_text)
        return self._dispatch_user_hooks(event)


def make_engine(brand: BrandConfig) -> HookEngine:
    return HookEngine(brand, brand.resolved_config_dir)


# Type alias for the agent's "give me a hook for X" indirection.
HookHandler = Callable[..., list[str]]
