---
name: code-sandbox
description: Run Python/JS/Bash safely in isolated sandbox for testing & function execution
---

# Code Execution Sandbox Skill

Runs arbitrary code (Python, JavaScript, Bash) in a **sandboxed** subprocess —
isolated filesystem, network off, timeout-bounded, output-capped. Used for unit
tests, quick proofs-of-concept, or executing reported agent functions.

## Mechanism (see `src/dhybrid/tools/terminal.py` — sandbox mode + `subagents`)

- **Process isolation** — child process in a temp dir; cwd != project root.
- **Network deny** — set `NETWORK=0` env; block outbound by sandboxing layer.
- **File jail** — read only allowlisted files (passed via stdin/mount); never touch
  `~/.dhybrid` or workspace parent dirs.
- **Resource caps** — runtime <= 30s (configurable), stdout <= 4KB cap.
- **Language dispatch** — `python3`, `node`, `bash` via shebang or `--lang <p|j|b>`.

## Policies

1. **No secrets to sandbox** — env vars are scrubbed; only pass `PUBLIC_*` explicitly.
2. **No persistent write** — sandbox FS is temp & deleted after run; outputs come back
   via stdout (capped), never by writing to workspace.
3. **Timeout kills** — `timeout` enforced by OS; child killed on exceed (no orphan).
4. **Output sanitized** — only final stdout returned; stderr captured & summarized
   (truncated) so raw traceback doesn't leak huge stacks.
5. **Rate limit** — max 2 sandbox runs per tool-block (avoid CPU hogging host).

## Commands (REPL / tool)

- `/sandbox run "<code>"` — auto-detect language by content; run.
- `/sandbox run --lang python "<code>"` — force Python 3.12.
- `/sandbox run --lang node "<code>"` — force Node.
- `/sandbox run --lang bash "<code>"` — force Bash.
- `/sandbox test <path>` — run a single test file inside sandbox (pytest -q).
- `/sandbox eval "<expr>"` — one-liner eval (Python default).

## Recommended flow

```
/sandbox run --lang python "
import hashlib
def sha(x): return hashlib.sha256(x.encode()).hexdigest()[:8]
print(sha('hello'))
"
```

## Lazy pattern (token savings)

- Reuse prior sandbox result if same-code submitted within session (cache keyed by
  sha256(code+lang)).
- Don't sandbox what `grep`/`read` already answer (lazy senior policy).
- Truncate stdout to first 100 lines / 4000 chars before returning to LLM.

## Trigger

User sebut: "run", "execute", "coba", "test", "eval", "proof of concept",
"kode", "python", "node", "bash", syntax like `python3 -c`, `node -e`, `echo`.

## Safety blocks

- `rm -rf`, `chmod 777 /`, `:(){` — rejected by `src/dhybrid/tools/security.py`
  before reaching sandbox.
- outbound network — dropped at process boundary.
- no `--privileged` / no container-escape primitives allowed.

## Verification

- [ ] `/sandbox run "print(1+1)"` → `2`, exit 0.
- [ ] `/sandbox run --lang bash "exit 5"` → nonzero exit, error surfaced.
- [ ] stdout cap enforced (submit >4KB output → truncated + `[truncated]`).
- [ ] timeout enforced (`<code dengan sleep 100` → killed before 30s).
- [ ] no env secret visible inside sandbox (`print(os.environ)` doesn't leak).
