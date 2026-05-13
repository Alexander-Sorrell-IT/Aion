---
name: structured-logging
description: Add or improve structured logging. Use when the user asks to "add logging", "what should I log here", "improve logs", or has logs that aren't useful when debugging production. Distinguishes signal from noise.
---

# structured-logging

Logs exist for ONE reason: helping you understand what happened in production when something went wrong. Logs that don't serve that purpose are noise. This skill keeps the signal-to-noise ratio honest.

## When to act

- User wants to add logging to existing code
- User says their logs aren't useful in production
- New feature needs instrumentation

## When not to act

- User just wants `console.log` while developing (use a real debugger, or local-only logging)
- User has a clear logging library and is asking about syntax (point at docs)

## What to log

### Always log

- **Entry/exit of request handlers** — with request ID, user ID (or "anonymous"), endpoint, method, status code, duration
- **External calls** — outbound HTTP, DB queries (NOT the full SQL with bound values), queue publishes. Log: target, duration, success/failure.
- **State transitions** — "user upgraded to plan X", "order moved from pending to paid"
- **Errors** — every catch block that doesn't immediately propagate. Include the exception type, message, and STACK TRACE.
- **Crashes** — uncaught exceptions, panics. With full context.

### Sometimes log

- Long-running operations (loop iteration counts, batch sizes) — useful for tracking progress, can be noisy if overdone
- Cache hits/misses — useful for tuning but high-volume
- Authentication events — login success/failure (without revealing whether the username exists)

### Never log

- Passwords, tokens, API keys, session IDs (even partially — first/last 4 chars is still risk)
- Full request bodies that may contain credentials
- PII unless your compliance posture explicitly permits
- Health-check requests at INFO level (they swamp the log)
- "Every line of execution" (this is what tracing is for)

## How to log

### Structured, not free-form

Bad:
```
log.info(f"User {user_id} just placed order {order_id} for ${amount}")
```

Good:
```python
log.info("order placed", user_id=user_id, order_id=order_id, amount=amount)
```

The structured version is queryable: "show me all orders for user X today" becomes a filter, not a regex.

### Levels mean something

- **DEBUG** — diagnostic detail; off in production by default
- **INFO** — normal lifecycle events; happy path
- **WARN** — something unusual; the request succeeded but you want to look at it
- **ERROR** — failure; the request did not succeed
- **CRITICAL/FATAL** — the service is impaired; usually triggers paging

Don't log "user not found" as ERROR. That's a normal client-side mistake. WARN at most; usually nothing.

### Correlation IDs

Every request gets a unique ID at the edge. Pass it through every log line for that request. Then "show me everything that happened for request X" becomes one query.

Most frameworks have request-context middleware that injects this. Use it.

### Don't log inside hot loops

A loop running 1M times shouldn't log every iteration. Either log summaries (every 10k, or at start/end) or use sampling.

## Common mistakes

- **No request ID** — can't correlate log lines for the same request across services
- **Logging the same event from 3 places** — once is enough; pick the right layer
- **Free-form messages** — `f"X happened with values {a}, {b}"` is unqueryable; use structured fields
- **Logging full responses** — fills the log with bytes you'll never read
- **No log levels** — everything at INFO; you can't filter to what matters
- **Print statements instead of a logger** — print goes to stdout regardless of environment; the logger respects level + destination config
- **Sensitive data** — most catastrophic; can take legal action to clean up after the fact
