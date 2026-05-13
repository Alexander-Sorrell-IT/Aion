# mcp-server-dev

Build MCP servers (the protocol Proteus uses to talk to external tools). Complements `plugin-dev/mcp-integration` which covers wiring an existing server into a plugin — this plugin covers building one from scratch.

| Skill | Triggered by |
|---|---|
| `mcp-server-design` | "build an MCP server", "design an MCP integration from scratch" |

Covers transport selection (stdio/SSE/HTTP/WebSocket), tool surface design, resource surface design, structured error handling, server lifecycle, and common pitfalls.
