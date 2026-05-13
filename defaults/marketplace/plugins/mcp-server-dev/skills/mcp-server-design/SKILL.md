---
name: mcp-server-design
description: Design an MCP server — picking transport, defining tools and resources, schema design, server lifecycle. Use when the user asks to "build an MCP server", "create an MCP integration from scratch", or "what should my MCP server expose?".
---

# mcp-server-design

The Model Context Protocol is the standard way an agent talks to an external tool/resource provider. Building a server means picking what to expose, in what shape, over what transport.

## When to act

- "Build an MCP server", "create an MCP server", "design an MCP integration"
- User has a backend service they want an agent to drive and is choosing how to expose it

## When not to act

- User wants to *use* an existing MCP server (different skill — see plugin-dev/mcp-integration)
- User is asking about MCP the protocol abstractly (point at docs, no design needed)

## Step 1 — pick the transport

| Transport | Use when |
|---|---|
| **stdio** | Server is a local process. Lowest latency, no network. Default choice for tools that ship as a binary. |
| **SSE** (Server-Sent Events) | Server is remote/hosted. Long-lived connection, streaming responses. The right choice for SaaS integrations. |
| **HTTP** | Stateless requests, no streaming needed. Rare; usually SSE is better. |
| **WebSocket** | Bidirectional real-time. Rare in MCP context. |

If unsure: stdio for self-contained tools, SSE for anything that lives on the network.

## Step 2 — design the tool surface

A tool is a function the agent can call. Each tool needs:

- **Name** — `verb-noun` form. `search-issues`, `create-pr`, `list-projects`. Don't pluralize verbs.
- **Description** — one paragraph, names exactly when to use it. The agent's tool-selection picks tools by description, so this is high-leverage.
- **Input schema** — JSON Schema describing the arguments. Strict types, required vs optional, descriptions for each field.
- **Output schema** — what the tool returns. Structured (JSON) > unstructured prose.

### How many tools

- One tool per CONCEPTUAL operation, not per API endpoint
- If two endpoints do the same thing with different params (`/users/{id}` vs `/users?email=`), one tool with optional fields
- If one endpoint does many things based on a flag, split into multiple tools

### Tool description quality

The agent reads only the description before deciding to call a tool. So:

- Lead with the action: "Search GitHub issues by repo and query."
- Name when to use: "Use when the user wants to find issues by text content, author, label, or status."
- Name when NOT to use: "Don't use for pull requests — use search-prs instead."

## Step 3 — design the resource surface (optional)

Resources are read-only data the agent can fetch by URI. Useful for:

- File-like content the agent might want to attach to context
- Logs or stream contents
- API responses that the user might want directly visible

If your server is purely action-oriented, skip resources.

## Step 4 — error handling

When a tool call fails, return a STRUCTURED error, not a string:

```json
{
  "error": {
    "type": "rate_limited",
    "message": "GitHub API rate limit exceeded, retry after 60s",
    "retry_after_seconds": 60
  }
}
```

The agent can act on structured errors. Strings get formatted and shown to the user but can't be programmatically handled.

## Step 5 — server lifecycle

For stdio: process spawned on session start, killed on session end. Keep startup fast (<1s). Lazy-init expensive resources after first tool call.

For SSE: long-lived connection. Implement keep-alive pings. Handle reconnection gracefully — clients drop connections often.

## Common pitfalls

- **Tools that are too generic** — `query-database(sql)` is useless; the agent has no idea what to query. Wrap with named operations.
- **Synchronous long-running operations** — block the agent. Either make tools fast or return a job ID and provide a `check-status` tool.
- **Authentication leaks** — passing API keys as tool arguments instead of via the server's own credential storage.
- **No idempotency** — `create-issue` called twice creates two issues. Either add an optional client-supplied dedup key, or document non-idempotency clearly.
- **Output size** — returning 10MB of logs blows the agent's context. Truncate, summarize, or expose a "get next page" tool.
