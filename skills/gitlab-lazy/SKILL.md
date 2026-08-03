---
name: gitlab-lazy
description: GitLab CI/CD + git via glab CLI — issues, MR, pipelines, read repo
---

# GitLab Skill (glab CLI + REST)

Drive GitLab via `glab` CLI + raw REST. Mirrors the GitHub skill but for GitLab
CI/CD, merge requests, and issues.

## Tools

| Tool | Purpose |
|------|---------|
| `glab` / terminal | `glab mr list`, `glab pipeline view`, `glab issue create`, etc. |
| `gh_api`-style | `glab api /projects/:id/merge_requests/:iid` (raw REST). |
| `read_file` | read repo files within workspace checkout. |

## Policies (same as GitHub skill — kebijakan seragam)

1. Inspect before mutate (`glab mr list --reviewer @me --state merged~`).
2. Branch per concern (`fix/`, `feat/`), CI green before merge.
3. Conventional commits.
4. Never push secrets; `glab auth login` uses token from env `GITLAB_TOKEN`
   (set via `/key gitlab` helper if extended).
5. Retry 429 via existing backoff (`src/dhybrid/llm/providers.py`).

## Commands (REPL)

- `/glab mr list [--mine] [--open]`
- `/glab issue list [--assigned]`
- `/glab pipeline view <ref|mr>`
- `/glab mr create "<title>" --target main --label bug,backend`
- `/glab mr diff <iid>`
- `/glab ci watch <ref>` — stream pipeline until green/✗.

## Flow (mirrors web-github skill)

```
1. glab mr list --mine --open
2. git checkout -b fix/gitlab-17 main && git pull
3. [edit]
4. glab mr create "Fix #17 ..." --target main --label bug
5. glab ci watch HEAD   # retry 429 otomatis
6. assign reviewer, monitor sampai hijau
```

## Trigger / keyword

User sebut: "gitlab", "mr", "merge request", "pipeline", "CI", "glab", "gitlab CI".

## Verifikasi

- [ ] `glab auth status` ok.
- [ ] `/glab mr list` returns real MRs.
- [ ] `/glab pipeline view HEAD` returns pipeline status (success/failed).
- [ ] `/glab mr create` returns MR URL.
- [ ] CI failure detected & surfaced (not silently ignored).
