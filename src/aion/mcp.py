"""MCP (Model Context Protocol) client — stdio servers only for v0.x.

MCP servers are subprocesses that speak JSON-RPC 2.0 over stdin/stdout.
They expose tools and resources the agent can consume. Aion treats them
as additional tool providers alongside the built-in tools.

Why hand-roll this instead of using the `mcp` SDK:
  - The official Python SDK is async-first; our agent loop is sync.
    Wrapping it would require asyncio.run() per call, plus event-loop
    juggling that's fragile inside a REPL.
  - Stdio JSON-RPC is ~150 lines of code. The dependency surface gain
    isn't worth the abstraction cost at this scope.
  - This file handles all of stdio. SSE/HTTP transports get added later
    as needed and can use the SDK's async client at that point if
    desired — they're a smaller subset of MCP usage in practice.

Discovery sources:
  <config>/mcp.json                — user-level server declarations
  <plugin>/.claude-plugin/plugin.json `mcp.servers` block — plugin-bundled

Each server gets prefixed tool names so they don't clash with built-ins
or other servers: `mcp_<server-name>_<tool-name>`. The prefix lets the
dispatcher route correctly.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── server config ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MCPServerConfig:
    """A declared MCP server. Read from mcp.json or a plugin's manifest."""
    name: str
    command: str  # the executable to spawn
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # only stdio supported for v0.x

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "MCPServerConfig":
        # Resolve $-style env var references in args (e.g. "${HOME}/bin/server")
        def _expand(s: str) -> str:
            return os.path.expandvars(s)

        return cls(
            name=name,
            command=_expand(str(d.get("command", ""))),
            args=[_expand(str(a)) for a in d.get("args", [])],
            env={k: _expand(str(v)) for k, v in (d.get("env", {}) or {}).items()},
            transport=str(d.get("transport", "stdio")),
        )


def load_user_mcp_servers(config_dir: Path) -> list[MCPServerConfig]:
    """Read <config>/mcp.json. Returns empty list if absent or malformed."""
    path = config_dir / "mcp.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    servers_raw = data.get("servers", {}) or {}
    return [MCPServerConfig.from_dict(name, cfg) for name, cfg in servers_raw.items()]


def load_plugin_mcp_servers(plugin_install_path: Path) -> list[MCPServerConfig]:
    """Read mcp.servers from a plugin's plugin.json."""
    manifest = plugin_install_path / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text())
    except json.JSONDecodeError:
        return []
    mcp_block = data.get("mcp", {}) or {}
    servers_raw = mcp_block.get("servers", {}) or {}

    # ${CLAUDE_PLUGIN_ROOT} / ${AION_PLUGIN_ROOT} expansion — point at the
    # plugin's install directory.
    plugin_root = str(plugin_install_path)
    expanded_servers: list[MCPServerConfig] = []
    for name, cfg in servers_raw.items():
        if isinstance(cfg, dict):
            cfg = {**cfg}
            cfg.setdefault("env", {})
            os.environ.setdefault("CLAUDE_PLUGIN_ROOT", plugin_root)
            os.environ.setdefault("AION_PLUGIN_ROOT", plugin_root)
        expanded_servers.append(MCPServerConfig.from_dict(name, cfg))
    return expanded_servers


# ── stdio JSON-RPC client ───────────────────────────────────────────────────


class MCPProtocolError(Exception):
    """Raised when the server returns a JSON-RPC error response."""


@dataclass
class MCPTool:
    """One tool exposed by an MCP server. Wrapped into our OpenAI-style
    tool schema by `to_openai_schema` so litellm can consume it."""
    name: str  # the SERVER's name for the tool (not prefixed)
    description: str
    input_schema: dict
    server_name: str

    @property
    def prefixed_name(self) -> str:
        return f"mcp_{self.server_name}_{self.name}"

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.prefixed_name,
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


class MCPServer:
    """One spawned MCP server subprocess + JSON-RPC client."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._tools: list[MCPTool] = []
        self._initialized = False

    def start(self) -> None:
        """Spawn the server subprocess. Idempotent."""
        if self._proc is not None and self._proc.poll() is None:
            return
        env = {**os.environ, **self.config.env}
        self._proc = subprocess.Popen(
            [self.config.command, *self.config.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,  # line-buffered so we can read response-by-response
        )

    def stop(self) -> None:
        """Terminate the server process. Safe to call multiple times."""
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        except Exception:
            pass
        self._proc = None
        self._initialized = False

    def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request, return the parsed response."""
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError(f"MCP server '{self.config.name}' is not running")

        req_id = str(uuid.uuid4())
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        with self._lock:
            assert self._proc.stdin is not None
            assert self._proc.stdout is not None
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()

            # Read until we get a response with our id (servers may emit
            # notifications between requests; we ignore those for now).
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    raise RuntimeError(
                        f"MCP server '{self.config.name}' closed stdout unexpectedly"
                    )
                try:
                    msg = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == req_id:
                    if "error" in msg:
                        raise MCPProtocolError(msg["error"])
                    return msg.get("result", {})
                # Otherwise it's a notification or out-of-order response; skip

    def _send_notification(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError(f"MCP server '{self.config.name}' is not running")
        request: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        with self._lock:
            assert self._proc.stdin is not None
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()

    def initialize(self) -> None:
        """Run the MCP initialize handshake."""
        if self._initialized:
            return
        self._send_request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "aion", "version": "0.1.0"},
            },
        )
        # Per MCP spec, send `notifications/initialized` after the response.
        self._send_notification("notifications/initialized")
        self._initialized = True

    def list_tools(self) -> list[MCPTool]:
        """Fetch the tools this server exposes."""
        result = self._send_request("tools/list")
        tools_raw = result.get("tools", [])
        self._tools = [
            MCPTool(
                name=str(t.get("name", "")),
                description=str(t.get("description", "")),
                input_schema=dict(t.get("inputSchema", {})),
                server_name=self.config.name,
            )
            for t in tools_raw
            if t.get("name")
        ]
        return self._tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """Invoke a tool. Returns the textual content of the result."""
        result = self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        # Result format: { content: [{ type: "text", text: "..." }, ...] }
        content_items = result.get("content", [])
        text_parts: list[str] = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        return "\n".join(text_parts) if text_parts else json.dumps(result)


# ── manager: lifecycle + tool routing for many servers ──────────────────────


_PREFIX_RE = re.compile(r"^mcp_([^_]+)_(.+)$")


class MCPManager:
    """Owns the set of MCP servers configured for this session. The CLI
    constructs one of these at startup, the agent consults it for tool
    schemas and tool-call routing.

    Lifecycle: spawn servers on construction (or lazily on first list);
    stop them on `shutdown()`. Wire shutdown into session_end if you want
    clean teardown.
    """

    def __init__(self, configs: list[MCPServerConfig]) -> None:
        self.configs = configs
        self.servers: dict[str, MCPServer] = {c.name: MCPServer(c) for c in configs}
        self._tools_cache: list[MCPTool] | None = None

    def start_all(self) -> dict[str, str | None]:
        """Spawn + initialize every server. Returns {name: error_message_or_None}.
        Errors don't raise — they're surfaced per-server so a single broken
        config doesn't take down the rest."""
        results: dict[str, str | None] = {}
        for name, server in self.servers.items():
            try:
                server.start()
                server.initialize()
                results[name] = None
            except Exception as e:  # noqa: BLE001 — surface to caller
                results[name] = str(e)
        return results

    def shutdown(self) -> None:
        """Stop every server process."""
        for server in self.servers.values():
            server.stop()
        self._tools_cache = None

    def all_tools(self) -> list[MCPTool]:
        """Aggregate tool list across every initialized server."""
        if self._tools_cache is not None:
            return self._tools_cache
        tools: list[MCPTool] = []
        for server in self.servers.values():
            if server._initialized:
                try:
                    tools.extend(server.list_tools())
                except Exception:  # noqa: BLE001
                    continue
        self._tools_cache = tools
        return tools

    def tool_schemas(self) -> list[dict]:
        """Tools converted to OpenAI-style function schemas. Returned to the
        agent so they get sent to the LLM alongside the built-in tools."""
        return [t.to_openai_schema() for t in self.all_tools()]

    def can_route(self, tool_name: str) -> bool:
        """Does this tool name look like an MCP-prefixed name we route?"""
        m = _PREFIX_RE.match(tool_name)
        if not m:
            return False
        server_name = m.group(1)
        return server_name in self.servers

    def dispatch(self, tool_name: str, arguments: dict) -> tuple[bool, str]:
        """Call a tool via its MCP server. Returns (ok, content)."""
        m = _PREFIX_RE.match(tool_name)
        if not m:
            return False, f"not an MCP tool: {tool_name}"
        server_name, real_name = m.group(1), m.group(2)
        server = self.servers.get(server_name)
        if server is None:
            return False, f"unknown MCP server: {server_name}"
        try:
            return True, server.call_tool(real_name, arguments)
        except MCPProtocolError as e:
            return False, f"MCP error: {e}"
        except Exception as e:  # noqa: BLE001
            return False, f"MCP call failed: {e}"
