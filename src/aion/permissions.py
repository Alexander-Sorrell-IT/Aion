"""Permission system — three orthogonal flags + named presets.

The three flags are independent so users can compose any combination:

  auto_accept_edits    — Edit/Write tools run without prompting; Bash still prompts
  bypass_permissions   — ALL tools run without prompting (the YOLO flag)
  plan_mode            — agent must produce a written plan before executing
                         (the human approves the plan, which sets execution flags)

Five named presets cover the common combinations the user actually picks:

  Careful   — all OFF (manual checkpoint on every action)
  Standard  — auto ON, bypass OFF, plan OFF  (the daily-driver default)
  Trusted   — auto ON, bypass ON,  plan OFF  (you trust this codebase)
  Planner   — auto OFF, bypass OFF, plan ON  (think before doing)
  YOLO Plan — auto ON, bypass ON,  plan ON   (plan then full-execute)

The 8th combination (auto OFF, bypass ON, plan OFF) is reachable via
direct toggles but isn't a named preset because it's weird: you bypass
all prompts AND don't auto-accept edits, which is a contradiction in
practice. Direct toggles let you express it; presets stay clean.

A separate per-tool override map lets advanced users say things like
"auto-accept Edit but ALWAYS prompt for Bash" — that's the kill feature
nobody else has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ToolKind(Enum):
    """Classify each tool for permission decisions."""
    READ_ONLY = "read_only"      # read, grep, glob — safe; never prompt
    FILE_WRITE = "file_write"    # write, edit — gated by auto_accept_edits
    SHELL = "shell"              # bash — gated by bypass_permissions
    EXTERNAL = "external"        # mcp_* — gated by bypass_permissions; user can per-server


_DEFAULT_TOOL_KINDS: dict[str, ToolKind] = {
    # Built-ins (tools.py)
    "read":  ToolKind.READ_ONLY,
    "grep":  ToolKind.READ_ONLY,
    "glob":  ToolKind.READ_ONLY,
    "write": ToolKind.FILE_WRITE,
    "edit":  ToolKind.FILE_WRITE,
    "bash":  ToolKind.SHELL,

    # Extras (extra_tools.py) — network-reading is closer to read-only than
    # to shell. The agent reads a URL or query result; no system side effects.
    "webfetch":       ToolKind.READ_ONLY,
    "websearch":      ToolKind.READ_ONLY,
    "todo_write":     ToolKind.READ_ONLY,  # session state only
    "ask_user":       ToolKind.READ_ONLY,  # user-driven; safe
    "agent_dispatch": ToolKind.EXTERNAL,   # spawns a subagent with its own tools

    # Tasks (tasks.py) — background subagents
    "task_create": ToolKind.EXTERNAL,
    "task_list":   ToolKind.READ_ONLY,
    "task_get":    ToolKind.READ_ONLY,
    "task_output": ToolKind.READ_ONLY,
    "task_update": ToolKind.READ_ONLY,
    "task_stop":   ToolKind.READ_ONLY,

    # Tier 2 (tier2_tools.py)
    "notebook_edit":   ToolKind.FILE_WRITE,  # writes a .ipynb file
    "enter_plan_mode": ToolKind.READ_ONLY,   # state toggle only
    "exit_plan_mode":  ToolKind.READ_ONLY,
    "config_get":      ToolKind.READ_ONLY,
    "config_set":      ToolKind.FILE_WRITE,  # writes settings.json
    "advisor":         ToolKind.EXTERNAL,    # external LLM call
}


def classify_tool(name: str) -> ToolKind:
    """Bucket a tool name into a kind for permission gating. MCP-prefixed
    tools (e.g. `mcp_github_create_pr`) classify as EXTERNAL."""
    if name in _DEFAULT_TOOL_KINDS:
        return _DEFAULT_TOOL_KINDS[name]
    if name.startswith("mcp_"):
        return ToolKind.EXTERNAL
    # Unknown tools default to SHELL — safest is "prompt unless bypass".
    return ToolKind.SHELL


@dataclass
class PermissionState:
    """Mutable permission state for the session. Lives for one REPL session
    or one one-shot invocation."""

    auto_accept_edits: bool = False
    bypass_permissions: bool = False
    plan_mode: bool = False

    # Per-tool overrides: tool_name → "allow_session" (skip future prompts for
    # this tool) | "deny_session" (always reject). None = use flags above.
    tool_overrides: dict[str, str] = field(default_factory=dict)

    # In non-interactive mode (one-shot, piped stdin), the gate can't actually
    # prompt. Setting this to True means "skip prompts altogether" without
    # touching bypass_permissions (which is a user-facing setting).
    noninteractive: bool = False

    def gate(self, tool_name: str) -> tuple[bool, str]:
        """Decide whether to run a tool. Returns (should_prompt, reason).

        If should_prompt is False, the tool runs immediately.
        If True, the REPL surfaces a prompt; the user's answer becomes the
        decision (and optionally a new tool_override).

        `reason` is a human-readable string the prompt shows (when prompting)
        or that gets logged (when allowing/denying without prompt).
        """
        # Per-tool override takes precedence over everything.
        ov = self.tool_overrides.get(tool_name)
        if ov == "allow_session":
            return False, f"session-allow override for {tool_name}"
        if ov == "deny_session":
            # Returning should_prompt=True with a deny reason; the gate caller
            # interprets this as "this tool is currently denied for the
            # session, surface that to the user."
            return True, f"session-deny override for {tool_name}"

        if self.bypass_permissions:
            return False, "bypass_permissions=True"

        kind = classify_tool(tool_name)

        if kind == ToolKind.READ_ONLY:
            return False, "read-only tool"

        if kind == ToolKind.FILE_WRITE and self.auto_accept_edits:
            return False, "auto_accept_edits=True"

        if self.noninteractive:
            # Can't prompt — best-effort: allow read-only and auto-allow file
            # writes (already handled above), but block shell/external in
            # non-interactive without an explicit bypass.
            if kind == ToolKind.READ_ONLY:
                return False, "non-interactive: read-only tool"
            # File writes here means auto_accept was False; block.
            return True, f"non-interactive mode and {kind.value} requires prompt"

        return True, f"{kind.value} requires user approval"


# ── named presets ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PermissionPreset:
    name: str
    description: str
    auto_accept_edits: bool
    bypass_permissions: bool
    plan_mode: bool


PRESETS: tuple[PermissionPreset, ...] = (
    PermissionPreset(
        name="Careful",
        description="Manual checkpoint on every action. Safest for new codebases.",
        auto_accept_edits=False,
        bypass_permissions=False,
        plan_mode=False,
    ),
    PermissionPreset(
        name="Standard",
        description="Auto-accept file edits; still prompt for shell. The daily default.",
        auto_accept_edits=True,
        bypass_permissions=False,
        plan_mode=False,
    ),
    PermissionPreset(
        name="Trusted",
        description="Bypass all prompts. Use only in codebases you fully trust.",
        auto_accept_edits=True,
        bypass_permissions=True,
        plan_mode=False,
    ),
    PermissionPreset(
        name="Planner",
        description="Plan first, execute after approval. Manual on each step.",
        auto_accept_edits=False,
        bypass_permissions=False,
        plan_mode=True,
    ),
    PermissionPreset(
        name="YOLO Plan",
        description="Plan first, then full-execute without prompts. The combo.",
        auto_accept_edits=True,
        bypass_permissions=True,
        plan_mode=True,
    ),
)


def find_matching_preset(state: PermissionState) -> PermissionPreset | None:
    """If the current state matches a named preset exactly, return it."""
    for p in PRESETS:
        if (
            p.auto_accept_edits == state.auto_accept_edits
            and p.bypass_permissions == state.bypass_permissions
            and p.plan_mode == state.plan_mode
        ):
            return p
    return None


def cycle_preset(state: PermissionState) -> PermissionPreset:
    """Advance to the next named preset. If state doesn't currently match
    any preset, start at Standard. Mutates state in place; returns the new
    preset for display purposes."""
    current = find_matching_preset(state)
    if current is None:
        target = PRESETS[1]  # Standard
    else:
        idx = PRESETS.index(current)
        target = PRESETS[(idx + 1) % len(PRESETS)]
    state.auto_accept_edits = target.auto_accept_edits
    state.bypass_permissions = target.bypass_permissions
    state.plan_mode = target.plan_mode
    return target


# ── status formatting ───────────────────────────────────────────────────────


def status_short(state: PermissionState) -> str:
    """One-line status for the bottom toolbar.

    Example: 'Auto: ON · Bypass: OFF · Plan: OFF · [Standard]'
    """
    def _b(v: bool) -> str:
        return "ON " if v else "OFF"
    preset = find_matching_preset(state)
    preset_tag = f" · [{preset.name}]" if preset else ""
    return (
        f"Auto: {_b(state.auto_accept_edits)} · "
        f"Bypass: {_b(state.bypass_permissions)} · "
        f"Plan: {_b(state.plan_mode)}{preset_tag}"
    )


def status_explained() -> str:
    """Full multiline help text for the `/perms` slash command."""
    lines = [
        "Permission flags",
        "================",
        "",
        "  Auto-accept edits   — Edit/Write tools run without prompting.",
        "                        Bash and external (MCP) tools STILL prompt.",
        "                        Toggle: Ctrl+A",
        "",
        "  Bypass permissions  — ALL tools run without any prompt.",
        "                        Includes Bash and dangerous commands.",
        "                        Use only in codebases you fully trust.",
        "                        Toggle: Ctrl+B",
        "",
        "  Plan mode           — Agent writes a plan first, you approve it,",
        "                        then it executes the plan with your chosen",
        "                        permission level.",
        "                        Toggle: Ctrl+P",
        "",
        "Read-only tools (read, grep, glob) never prompt regardless of flags.",
        "",
        "Named presets (cycle with Shift+Tab)",
        "------------------------------------",
    ]
    for p in PRESETS:
        flags = (
            f"auto={'ON' if p.auto_accept_edits else 'OFF'}, "
            f"bypass={'ON' if p.bypass_permissions else 'OFF'}, "
            f"plan={'ON' if p.plan_mode else 'OFF'}"
        )
        lines.append(f"  {p.name:11} ({flags})")
        lines.append(f"               {p.description}")
    return "\n".join(lines)


def collect_tool_overrides_summary(state: PermissionState) -> Iterable[tuple[str, str]]:
    """Yield (tool_name, override_value) pairs for `/perms` to render."""
    return state.tool_overrides.items()
