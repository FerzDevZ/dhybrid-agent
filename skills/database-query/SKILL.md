---
name: database-query
description: Run SQL/NoSQL queries, fetch analytics, generate data structure reports from DBs
---

# Database Query Skill (SQL / NoSQL)

Connect agent to SQL (Postgres/MySQL/SQLite) and NoSQL (MongoDB) for ad-hoc queries,
analytics snapshots, and structure reports. Queries are **read-mostly** by default;
writes require explicit `--write` flag + confirmation.

## Connectors (reuse `src/dhybrid/tools/` patterns)

| DB | Driver | DSN env var |
|----|--------|-------------|
| PostgreSQL | `psycopg` | `POSTGRES_DSN=postgres://user:pass@host:5432/db` |
| MySQL | `mysql-connector-python` | `MYSQL_DSN=mysql://user:pass@host:3306/db` |
| SQLite | stdlib `sqlite3` | `SQLITE_PATH=/abs/path.db` |
| MongoDB | `pymongo` | `MONGO_URI=mongodb://host:27017/db` |

## Policies

1. **Read-only default** — queries auto-wrapped in `BEGIN READ ONLY` (Postgres/MySQL);
   write/DDL requires `--write` + explicit `user.confirm`.
2. **Row cap** — max 100 rows returned (never dump whole tables); `LIMIT 100` auto-added.
3. **No secret in output** — mask PII columns (regex on `email`, `password`, `token`)
   before returning; configurable per-project.
4. **Schema-safe** — `db schema <table>` introspects structure first (columns, types)
   so generated queries don't typo.
5. **Idempotent analytics** — for dashboards, cache result 5 min (key on query hash).

## Commands (REPL / tool)

- `/db query "<SQL>"` — run query (read-only, capped 100 rows).
- `/db query --write "<SQL>"` — run write (asks confirm).
- `/db schema <table>` — print columns + types.
- `/db tables` — list tables (or collections).
- `/db report "<table>"` — auto-structure report: top 5 rows, row count, null %, indexes.

## Recommended flow

```
/db schema users
/db query "SELECT count(*) AS total, count(email) AS non_null_email FROM users"
-> result
/db query "SELECT email FROM users WHERE plan='free' LIMIT 100"
```

## NoSQL (MongoDB) variant

- `/db query mongo "select <coll> by {plan:'free'} fields {email:1} limit 100"`
- `/db report users` → analog: count, sample, index list.

## Lazy pattern (token savings)

- Cache `schema` + repeated analytics query (keyed by `(conn_id, query_hash)`)
  for 5 min; reuse result, note "[cached]".
- Truncate result to first 10 rows if >4KB; offer `[full]` on demand.

## Trigger

User sebut: "berapa banyak", "query", "sql", "mongodb", "count dari",
"laporan tabel", "analitik", "schema", "SELECT", "db.table".
Juga auto-trigger bila pertanyaan mengandung angka/statistik & DB conn terdaftar di env.

## Verification

- [ ] `/db schema <table>` returns real columns+types (typo-free).
- [ ] `/db query "SELECT 1"` → `1` (connection ok).
- [ ] result capped `LIMIT 100` — large query returns truncated.
- [ ] PII masked in output (no raw email/token).
- [ ] `--write` blocked without confirmation; DDL rejected in read-only conn.
