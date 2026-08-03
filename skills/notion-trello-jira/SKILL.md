---
name: notion-trello-jira
description: Manage project boards, create/update tickets, sync status across Notion, Trello, Jira
---

# Notion / Trello / Jira Skill

Manages project boards and tickets across Notion (API), Trello (REST), and Jira
(REST v3/Cloud). Keeps issue/trello card status in sync with agent progress,
so long-running tasks stay visible *outside* the agent loop.

## API surface (one adapter per service — all REST)

### Notion
- `POST https://api.notion.com/v1/pages` — create page (ticket) under a database.
- `PATCH https://api.notion.com/v1/pages/{page_id}` — update props (status, assignee).
- `POST https://api.notion.com/v1/databases/{db_id}/query` — list/search tickets.
- Auth: `Authorization: Bearer <NOTION_TOKEN>`; header `Notion-Version: 2022-06-28`.

### Trello
- `POST /1/cards` — create card (idList=LIST_ID, idMembers).
- `PUT /1/cards/{id}` — update name/desc/due/idList (move lists).
- `GET /1/lists/{id}/cards` — list cards; `GET /1/boards/{id}/lists`.
- Auth: `?key=KEY&token=TOKEN` query params.

### Jira Cloud
- `POST /rest/api/3/issue` — create issue (payload: fields.project, issuetype, summary).
- `PUT /rest/api/3/issue/{issueIdOrKey}` — edit (fields.status via `transition`? no — use transitions endpoint).
- `POST /rest/api/3/issue/{issueIdOrKey}/transitions` — move status (find transitions via GET).
- Auth: `Authorization: Basic base64(email:token)` (API token), `Content-Type: application/json`.

## Policies

1. **Create ticket on task accept** — when agent accepts a multi-step task,
   open a tracking ticket (status "in progress"). Link ticket ID to session.
2. **Status sync beats memory** — on step completion, PATCH ticket status
   (do→in-review/proof→done). Never leave ticket "in-progress" when agent exits.
3. **Idempotent updates** — fetch ticket state before mutating; skip if already at target
   status (avoids clobber + API round-trips).
4. **Secret hygiene** — tokens read from env (`NOTION_TOKEN`, `TRELLO_KEY`/`TRELLO_TOKEN`,
   `JIRA_EMAIL`/`JIRA_API_TOKEN`). No tokens in code; never echo them to logs.
5. **Board scope** — only act on boards the workspace explicitly owns (config list
   `board_ids`); never enumerate all boards (noisy, rate-limit risk).

## Commands (REPL)

- `/ticket list [board]` — list open tickets (filter by status != done).
- `/ticket create "<title>" [labels...]` — create new ticket (status=todo/in-progress).
- `/ticket link <ticket-id>` — bind current session to this ticket (sync start).
- `/ticket status <ticket-id> [status]` — get or set status; set calls transition API.
- `/ticket sync` — reconcile session progress vs linked ticket (move to done if all steps pass).

## Recommended flow

1. `/ticket create "Build auth module" auth,backend` → captures ticket ID.
2. Agent works (tests, commits). On each verified step, `/ticket status <id> in_review`.
3. At session end (or on verify), `/ticket sync` → transitions to `done` if green,
   `in_progress` if not.
4. Use `session_search`/`memory` to persist `<project>.<board>.ticket_ids` so next session
   resumes the same tickets.

## Safety / limits

- Max 1 API call per tool result block (avoid thundering herd / rate limits).
- Retry on 429 with exponential backoff (reuse `src/dhybrid/llm/providers.py` backoff).
- Jira Cloud: respect `X-RateLimit-remaining`; throttle if <10 remaining.
- Never delete boards/cards — only update status (irreversible ops need confirmation).

## Trigger

User mentions: "create ticket", "update jira", "notion page", "trello card",
"sync status", "link session to issue". Also auto-sync on session resume if
`memory` has a `project.<cwd>.ticket_id`.

## Verification

- [ ] token env vars set & tested (one read-only GET succeeds).
- [ ] `/ticket create` returns real ticket URL (not just ID).
- [ ] `/ticket status` idempotently transitions (no error on already-target).
- [ ] no secret leaked to logs/skill output.
- [ ] `/ticket sync` reconciles green build → done automatically.
