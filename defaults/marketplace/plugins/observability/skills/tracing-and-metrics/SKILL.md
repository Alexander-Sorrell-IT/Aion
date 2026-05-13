---
name: tracing-and-metrics
description: Add distributed tracing or metrics to a service. Use when the user asks to "add tracing", "add metrics", "instrument for OpenTelemetry", or wants to measure latency / throughput / error rates in production.
---

# tracing-and-metrics

Logs answer "what happened". Metrics answer "how much / how fast / how often". Traces answer "what was the chain of events for this one request". All three are different, all three matter.

## When to act

- User wants to add OpenTelemetry, Prometheus metrics, or similar instrumentation
- "How do I measure X" where X is performance or error rate
- Reviewing existing instrumentation that isn't giving useful signal

## When not to act

- User just wants logs (different skill)
- The service has zero users and over-instrumenting is premature

## Metrics — what to expose

### Counters (always-increasing)

- `http_requests_total{method, route, status}` — total HTTP requests
- `errors_total{type, component}` — total errors
- `events_processed_total{event_type}` — anything you process in batches/streams

### Gauges (current value)

- `active_connections` — currently open
- `queue_depth` — items waiting
- `worker_pool_size`

### Histograms (distribution of values)

- `http_request_duration_seconds{route}` — latency
- `db_query_duration_seconds{query_name}` — DB latency
- `payload_size_bytes` — request/response sizes

Histograms (NOT averages) for anything time-related. Averages hide tail latency; p99 is the metric that matters.

### Naming conventions

- snake_case
- Suffix the unit: `_seconds`, `_bytes`, `_total` (for counters)
- Label cardinality matters — `{user_id}` as a label produces N metrics per user; usually wrong. Use `{user_tier}` instead.

## Tracing — what to span

A trace is a tree of spans. Each span represents one operation. The root span is the entire request; children are sub-operations.

### What to make a span

- Request handlers (root span)
- DB queries
- External HTTP calls (with the target service as an attribute)
- Background jobs (in their own trace, with a link to the parent if relevant)
- Long-running operations (>10ms typically)

### What NOT to span

- Tight loop iterations (overhead exceeds the value)
- Function calls that always complete in <1ms (noise)
- Internal-only function calls that have no I/O

### Span attributes

Every span should have:
- A descriptive name (`http.GET /api/users/:id`, `db.SELECT users`)
- Attributes naming what was operated on (`user.id=...`, `db.table=...`)
- Status (ok / error) with error message if applicable

## Sampling

In high-traffic services, capturing every trace is wasteful. Sample:
- 100% in dev/staging
- 1–10% in production
- Always-capture for errors (the interesting traces)

## What to wire FIRST

If the service has nothing:
1. Request counter + duration histogram (gives you RPS and p50/p95/p99 latency)
2. Error rate counter (gives you health alarms)
3. A handful of tracing spans (root + critical sub-ops)

That's enough for a real dashboard. Add more once you know what you wish you had.

## Common mistakes

- **High-cardinality labels** — `{trace_id}`, `{user_id}`, `{request_id}` as labels = unbounded metric series; will OOM your TSDB
- **Tracing everything** — overhead becomes significant in tight code paths
- **Metrics without alerting** — you wouldn't notice if the service died; metrics are useless without alarms on them
- **Custom timer code** — `start = now(); ... duration = now() - start; metric.record(duration)` is reinventing what histograms already do
- **No SLO** — measuring is pointless if you don't decide what's "OK". Set a target ("p95 < 200ms") and alert on its violation.
