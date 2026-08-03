---
name: web-github
description: Operate GitHub via gh REST + git: read files, PRs, issues, run CI, create PR
---

# GitHub Skill (gh CLI + REST)

Drive GitHub through the `gh` CLI + raw REST, wrapped by dhybrid tools.

## Tools (see `src/dhybrid/tools/github.py`)

| Tool | Purpose |
|------|---------|
| `gh` / terminal | wrapper: `gh pr list`, `gh pr checkout`, `gh run watch`, etc. |
| `gh_api` | raw `gh api <endpoint>` (REST v3 / GraphQL) for flexible queries. |
| `read_file`/`search_files` | read repo files (respecting workspace checkout). |

## Policies

1. **Read-before-write** — always inspect current state (`gh pr list`, `gh issue status`)
   before proposing changes; never assume branch/PR state.
2. **Branch per concern** — create `feat/<topic>` or `fix/<topic>` off `main`;
   don't commit to main directly.
3. **Commit hygiene** — small focused commits, conventional messages (`feat:`, `fix:`,
   `test:`). See `skills/git-workflow`.
4. **No blind pushes** — push only after local test pass; surface CI result
   (`gh run watch --exit-status`).
5. **PR review** — open PR with template + linked issues; post summary comment,
   don't inline every comment in chat (noisy).

## Commands (REPL)

- `/gh pr list [--mine] [--open]` — list PRs (filter mine/open).
- `/gh issue list [--mine]` — list issues assigned to you.
- `/gh create-branch <name>` — `git checkout -b <name>`.
- `/gh pr create "<title>" --body "<desc>" --reviewer "<user>"` — open PR.
- `/gh pr diff <pr|head>` — show diff of a branch/PR.
- `/gh run <pr|branch>` — watch CI status (auto-retry flaky on 429).

## Recommended flow

```
1. /gh pr list --mine          # apa yang belum selesai
2. gh checkout <base> && git pull
3. git checkout -b fix/issue-17
4. [edit code]                 # apply_patch / write_file
5. /gh run .                   # jalankan CI; retry 429 otomatis (lihat loop.py backoff)
6. /gh pr create "Fix #17 ..." --body "..." --reviewer "..."
7. monitor /gh run sampai hijau, baru merge/comment
```

## Trigger

User sebut: "buat branch", "commit", "buka pr", "review pr", "issue", "CI",
"gh pr", "gh issue", "merge conflict", "rebase".

## Verification

- [ ] `gh auth status` ok (terhubung repo remote).
- [ ] `/gh pr list` returns real PR data.
- [ ] `/gh create-branch fix/x` succeeds & `git branch` shows it.
- [ ] `/gh pr create` returns a real PR URL.
- [ ] no secret/token printed (gh handles auth via `~/.config/gh/hosts.yml`).
