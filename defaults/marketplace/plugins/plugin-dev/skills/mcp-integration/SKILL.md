---
name: mcp-integration
description: Wire an MCP (Model Context Protocol) server into a plugin — server types (stdio, SSE, HTTP), configuration in plugin.json or .mcp.json, ${CLAUDE_PLUGIN_ROOT} usage. Use when the user asks to "add an MCP server", "integrate MCP", "configure MCP", or mentions stdio/SSE/HTTP MCP transport.
---

# mcp-integration

MCP (Model Context Protocol) is the standard for connecting external tool/resource providers to an agent. A plugin can ship its own MCP server, or declare a dependency on one.

## Server transports

| Transport | Use when |
|---|---|
| `stdio` | Server is a local process (binary, script). Most common. Plugin ships the binary, runtime spawns it. |
| `sse` | Server is HTTP-based with Server-Sent Events. Used for remote hosted services. |
| `http` | Stateless HTTP. Less common; SSE is preferred for streaming. |
| `websocket` | Real-time bidirectional. Rare in plugin context. |

## Declaration

Option A — inside `plugin.json`:

```json
{
  "name": "my-plugin",
  "mcp": {
    "servers": {
      "my-server": {
        "command": "${CLAUDE_PLUGIN_ROOT}/bin/server",
        "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"]
      }
    }
  }
}
```

Option B — separate `.mcp.json` at plugin root:

```json
{
  "servers": {
    "my-server": {
      "transport": "stdio",
      "command": "${CLAUDE_PLUGIN_ROOT}/bin/server"
    }
  }
}
```

## ${CLAUDE_PLUGIN_ROOT}

The runtime substitutes this with the absolute path to the plugin's install directory. Use it everywhere you'd otherwise need an absolute path. Never hardcode `/home/...` or `~/.proteus/plugins/...`.

## stdio server example

```json
{
  "servers": {
    "code-search": {
      "transport": "stdio",
      "command": "node",
      "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"],
      "env": {
        "INDEX_PATH": "${CLAUDE_CONFIG_DIR}/code-search-index"
      }
    }
  }
}
```

The runtime spawns `node ${CLAUDE_PLUGIN_ROOT}/server.js`, pipes JSON-RPC over stdin/stdout, and exposes the server's tools to the agent.

## SSE / HTTP server example

```json
{
  "servers": {
    "remote-api": {
      "transport": "sse",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

Environment variables in headers/args/url get substituted from the user's shell env.

## Authentication

For servers that need user-level auth (OAuth flows, API tokens), the runtime provides an authentication harness:

```json
{
  "name": "gmail",
  "transport": "sse",
  "url": "https://...",
  "auth": {
    "type": "oauth",
    "flow": "device-code"
  }
}
```

The runtime walks the user through auth on first use and caches credentials.

## Common mistakes

- **Hardcoded paths** — breaks the plugin on any user's machine but yours
- **Missing transport field** — runtime can't tell stdio from SSE
- **Server crashes on startup** — runtime swallows the error silently; test the command manually first
- **Slow startup** — every session pays the latency; lazy-init expensive resources

## Verify a server works

```bash
proteus doctor   # health-checks all stdio servers
```

This spawns each server briefly and reports failures. Run before shipping a plugin.
