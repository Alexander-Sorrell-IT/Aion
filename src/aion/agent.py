"""Agent loop. The shape:

    1. Receive a user message
    2. Send conversation history + tool schemas to the LLM
    3. If the LLM responds with tool calls, dispatch each, append observations
    4. Loop until the LLM stops calling tools (finish_reason='stop')
    5. Return control to the user

This is provider-agnostic via litellm — the same loop works against OpenAI,
Anthropic, DeepSeek, Bedrock, Vertex, local Ollama, etc.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import BrandConfig
from .hooks import HookEngine
from .mcp import MCPManager
from .permissions import PermissionState
from .plugins.types import Plugin
from .tools import TOOL_SCHEMAS, ToolResult, dispatch


def build_system_prompt(brand: BrandConfig, plugins: list[Plugin] | None = None) -> str:
    """Construct the system prompt from brand config + active plugins.

    Identity modes:
      off     — generic "You are an AI assistant" prompt
      partial — "You are <display>, a configurable agent CLI." + tagline
      full    — partial + any brand.prompts.prepend additions

    Skills from active plugins are advertised in a "## Available skills" block
    so the model knows what description-triggered help is available. The model
    decides whether to load a skill's body on demand (via a skill-load tool
    that we'd add in a later iteration); for v0.1 the skill descriptions are
    visible at all times.
    """
    mode = brand.model_identity.mode

    if mode == "off":
        base = "You are an AI assistant operating as a CLI agent. You have access to tools for running shell commands, reading and writing files, and searching code. Use them deliberately."
    else:
        tagline = f" {brand.tagline}" if brand.tagline else ""
        base = (
            f"You are {brand.display}, a configurable agent CLI.{tagline} "
            "You have access to tools for running shell commands, reading and writing files, "
            "and searching code. Use them deliberately. Before acting, briefly state what "
            "you're about to do; after, briefly state what happened."
        )

    parts = [base]

    if plugins:
        skill_lines: list[str] = []
        for p in plugins:
            for s in p.skills:
                # Only the description goes in the system prompt — bodies are
                # loaded on-demand to stay light on context.
                skill_lines.append(f"- **{s.name}** — {s.description}")
        if skill_lines:
            parts.append(
                "## Available skills\n"
                "These skills are loaded and available. Each was contributed by an "
                "installed plugin. Use a skill when its description matches the task; "
                "ignore it otherwise.\n\n" + "\n".join(skill_lines)
            )

    composed = "\n\n".join(parts)
    if brand.prompts.prepend:
        return f"{brand.prompts.prepend}\n\n{composed}"
    return composed


@dataclass
class Message:
    """One conversation turn. Mirrors the OpenAI chat-completions shape so we
    can pass these straight to litellm.completion without transformation."""
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class Agent:
    brand: BrandConfig
    history: list[Message] = field(default_factory=list)
    # UI hook — invoked after each tool call so the CLI can render progress.
    # Receives (tool_name, arguments_dict, result_text, ok).
    on_tool_result: Callable[[str, dict, str, bool], None] | None = None
    # UI hook — invoked before each LLM call so the CLI can show a spinner.
    on_think: Callable[[], None] | None = None
    # UI hook — invoked when the assistant message has user-facing text content.
    on_assistant_text: Callable[[str], None] | None = None

    plugins: list[Plugin] = field(default_factory=list)
    hooks: HookEngine | None = None
    mcp: MCPManager | None = None
    permissions: PermissionState | None = None
    # UI callback for permission prompts. Receives (tool_name, args, reason)
    # and returns one of: "allow", "deny", "allow_session", "deny_session".
    # If not set, defaults to "allow" (no-prompt behavior — backward-compatible).
    on_permission_prompt: Callable[[str, dict, str], str] | None = None

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(
                Message(
                    role="system",
                    content=build_system_prompt(self.brand, self.plugins),
                )
            )

    def _call_llm(self) -> Any:
        # Lazy import so importing this module doesn't pay the litellm cost.
        from litellm import completion  # type: ignore[import-not-found]

        if self.on_think:
            self.on_think()

        # Merge built-in tools with any MCP tool schemas so the model sees
        # both as a single function-list. MCP tools are prefixed mcp_<server>_<name>
        # so they can never name-clash with built-ins.
        tools = list(TOOL_SCHEMAS)
        if self.mcp:
            tools.extend(self.mcp.tool_schemas())

        params: dict[str, Any] = {
            "messages": [m.to_dict() for m in self.history],
            "tools": tools,
        }
        # Model: brand override > env var > litellm default
        model = self.brand.api.model or os.environ.get("AION_MODEL") or "gpt-4o-mini"
        params["model"] = model
        if self.brand.api.base_url:
            params["api_base"] = self.brand.api.base_url

        return completion(**params)

    def execute(self, user_text: str) -> str:
        """Run one user turn to completion. Returns the assistant's final text."""
        self.history.append(Message(role="user", content=user_text))
        final_text = ""

        while True:
            response = self._call_llm()
            choice = response.choices[0]
            msg = choice.message

            # Extract assistant content + tool calls
            content = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None) or []

            # Record the assistant turn before running any tool calls so the
            # tool-result messages reference a tool_call_id the model already saw.
            assistant_msg = Message(
                role="assistant",
                content=content,
                tool_calls=[tc.model_dump() if hasattr(tc, "model_dump") else tc for tc in tool_calls]
                or None,
            )
            self.history.append(assistant_msg)

            if content and self.on_assistant_text:
                self.on_assistant_text(content)
            if content:
                final_text = content

            # No tool calls? Loop done — model is responding to the user, not requesting actions.
            if not tool_calls:
                break

            for tc in tool_calls:
                # litellm normalizes responses but the tool_call shape can vary.
                # Pull name + arguments defensively.
                fn = getattr(tc, "function", None) or tc.get("function", {})
                tool_name = (
                    getattr(fn, "name", None) if hasattr(fn, "name") else fn.get("name")
                )
                raw_args = (
                    getattr(fn, "arguments", "{}")
                    if hasattr(fn, "arguments")
                    else fn.get("arguments", "{}")
                )
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except json.JSONDecodeError:
                    arguments = {}

                tc_id = getattr(tc, "id", None) if hasattr(tc, "id") else tc.get("id", "")

                # PreToolUse hook — any returned text gets added to context.
                if self.hooks and tool_name:
                    pre_msgs = self.hooks.pre_tool_use(tool_name, arguments)
                    for m in pre_msgs:
                        self.history.append(Message(role="system", content=m))

                # Permission gate. If the gate says "should prompt", consult
                # the UI callback (which the REPL wires up); if no callback,
                # default-allow so non-interactive callers (one-shot, tests)
                # don't hang.
                allow = True
                deny_reason: str | None = None
                if self.permissions and tool_name:
                    should_prompt, reason = self.permissions.gate(tool_name)
                    if should_prompt:
                        if self.on_permission_prompt:
                            decision = self.on_permission_prompt(tool_name, arguments, reason)
                        else:
                            # No UI to prompt → allow. Backward-compatible.
                            decision = "allow"
                        if decision == "deny":
                            allow = False
                            deny_reason = f"User denied: {reason}"
                        elif decision == "deny_session":
                            allow = False
                            deny_reason = f"User denied (session): {reason}"
                            self.permissions.tool_overrides[tool_name] = "deny_session"
                        elif decision == "allow_session":
                            self.permissions.tool_overrides[tool_name] = "allow_session"
                            # fall through to run

                if allow:
                    # Route to MCP if the tool name matches a prefixed MCP tool;
                    # otherwise the built-in dispatcher handles it.
                    if self.mcp and tool_name and self.mcp.can_route(tool_name):
                        ok, content = self.mcp.dispatch(tool_name, arguments)
                        result = ToolResult(ok=ok, content=content)
                    else:
                        result = dispatch(tool_name or "", arguments)
                else:
                    result = ToolResult(ok=False, content=deny_reason or "denied")

                if self.on_tool_result:
                    self.on_tool_result(tool_name or "?", arguments, result.content, result.ok)

                # PostToolUse hook — runs memory-git autocommit + user hooks.
                if self.hooks and tool_name:
                    post_msgs = self.hooks.post_tool_use(tool_name, arguments, result.ok)
                    for m in post_msgs:
                        self.history.append(Message(role="system", content=m))

                self.history.append(
                    Message(
                        role="tool",
                        tool_call_id=tc_id,
                        name=tool_name,
                        content=result.content,
                    )
                )

            # Loop again — the model now sees the tool results and decides
            # whether to call more tools or respond to the user.

        return final_text
