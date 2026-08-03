---
name: api-http-request
description: Fire dynamic REST API calls to 3rd-party services with auth, schema, retry
---

# API Call / HTTP Request Skill

Fires dynamic REST API calls to third-party services from inside agent — with
structured headers, auth tokens, retry/backoff, and schema-aware response parsing.

## Mechanism (reuse `src/dhybrid/tools/web.py` or dedicated `http_request` tool)

- Built on `httpx.AsyncClient` (already a dep).
- Headers/body templated from `memory` (e.g. `auth.github.token`).
- Response parsed JSON (or raw text) → capped output (8KB), keys surfaced.
- Retry on 429/50x with exponential backoff (`src/dhybrid/llm/providers.py` backoff).

## Policies

1. **Secret hygiene** — tokens never logged; redact `Authorization`/`api_key` from output.
2. **Schema awareness** — optional `--schema` describes expected keys; validate & warn on mismatch.
3. **Dry-run first** — for state-changing calls (`POST/PUT/DELETE`), print summary
   + ask confirm before sending.
4. **Rate respect** — 1 call per result-block unless batch declared; honor `Retry-After`.
5. **Timeout-bound** — hard 30s per call; stream=False (headless, no SSE chunking).

## Commands (REPL / tool)

- `/api call <method> <url> [--header k:v] [--json '{...}']` — fire request.
- `/api save <name> <url>` — register API endpoint to memory (`api.<name>`).
- `/api run <name> --json '{...}'` — call a registered endpoint (headers auto-filled from memory).
- `/api schema <name>` — show registered schema/expected payload.
- `/api history` — list last 8 calls (method+url+status, not body).

## Auth patterns (store in memory/env, never inline)

- **Bearer**: memory `api.<name>.token` → `Authorization: Bearer <token>`.
- **API key**: memory `api.<name>.key` → header `X-API-Key: <key>` (varies by service).
- **Basic**: `BASE64(user:token)` → `Authorization: Basic ...`.

## Recommended flow

```
/api save github.repos https://api.github.com/repos/<owner>/<repo>
/api run github.repos --header "Authorization: Bearer $GITHUB_TOKEN"
-> {status, full_name, ...}  (parsed, truncated)
```

## Lazy pattern (token savings)

- Cache GET responses 5 min keyed by `(url, normalized_query)` — reuse, note `[cached]`.
- Truncate JSON to 20 keys / 8KB before returning; `[full]` on demand.
- Reuse registered `@api.<name>` instead of retyping URL+headers (lazy senior).

## Trigger

User sebut: "API", "request", "POST /users", "GET https://", "curl",
"fetch", "webhook", "auth header", plus any URL starting `http` — route through
`/api call` (not raw terminal `curl`, for auth safety).

## Verification

- [ ] `/api call GET https://httpbin.org/get` succeeds (200, parsed JSON).
- [ ] auth header redacted in output (`Authorization: [REDACTED]`).
- [ ] 429 auto-retried once with backoff.
- [ ] POST/PUT asks confirm before sending (dry-run summary).
- [ ] timeout enforced (30s).
