# DHYBRID SKILL EXPORT
**Exported at:** 2026-08-03  
**Source:** dhybrid-agent/skills/  
**Format:** Professional Markdown

---

## 1. Code Review

**Trigger:** When reviewing code for correctness, security, quality, and performance.

### Checklist (in order):
1. **Correctness** — logic, edge cases, error handling.
2. **Security** — injection, path traversal, hardcoded secrets, unvalidated input.
3. **Quality** — duplication, naming clarity, function length, misleading comments.
4. **Performance** — unnecessary complexity, loops in queries.

### Guidelines:
- Feedback: specific (`file:line`), concise, with concrete improvement suggestions.
- Avoid requesting large refactors without justification (YAGNI principle).

---

## 2. Debugging

**Trigger:** When debugging errors traceback or system issues systematically.

### Workflow:
1. Read the full error first: message, traceback, line number, file name.
2. Reproduce: run with the smallest input that triggers the error.
3. Find root cause (ask "why" three times), not just symptoms.
4. Check assumptions: data types, input values, boundary conditions.
5. Fix ONE cause, verify with smallest test, then proceed.

### Prohibitions:
- Guessing/random changes
- Changing many things at once
- Suppressing exceptions without understanding

---

## 3. Documentation

**Trigger:** When writing documentation, README, docstrings, or useful comments.

### Standards:
- **README**: What it does, how to install, usage examples, structure.
- **Docstrings**: What function does + important parameters (not restating code).
- **Comments**: Explain WHY (decision reasoning), not WHAT (code is self-evident).
- **Language**: Match the project's language and audience.

### Notes:
- Keep documentation concise; don't write lengthy docs for simple functions.
- Lazy rule: document only if it adds value, not to meet quotas.

---

## 4. Git Workflow

**Trigger:** When committing, branching, or reviewing git operations.

### Conventional Commit Messages:
- `feat:` new feature
- `fix:` bug fix
- `refactor:` code restructuring without behavior change
- `test:` add/modify tests
- `docs:` documentation
- `chore:` technical tasks
- `ci:` pipeline changes
- `perf:` performance improvements

### Rules:
- Small, focused commits (one change per commit)
- Never commit generated files or secrets (`.env`, build output) — check `git status` first
- Run tests before pushing
- Avoid `git push --force` on shared branches

---

## 5. Lazy Senior Dev

**Trigger:** When making code changes — always prefer minimal, justified action.

### Philosophy:
"Best code = code never written." Before writing anything, ask:

1. Is this feature actually requested? (YAGNI)
2. Is there already a helper/library that can be reused? (grep first)
3. What is the SMALLEST edit that solves the problem?

### Red Flags (DO NOT):
- Refactor without being asked
- Rewrite entire files when only a few lines changed (use targeted patches)
- Add abstractions "just in case"

### Rule:
If nothing needs changing: say "TIDAK ADA YANG PERLU DIUBAH" (Nothing needs to be changed).

---

## 6. Performance Optimization

**Trigger:** When optimizing performance or investigating bottlenecks.

### Process:
1. **Measure first** — profile (time, call counts) before optimizing; no data, no optimization.
2. Find the biggest bottleneck (common: nested loops, repeated queries, I/O).
3. Fix with the smallest change possible:
   - Hoist calculations out of loops
   - Cache repeated results
   - Avoid O(n²) → O(n) where straightforward
   - Limit I/O (read once, process many)
4. Verify: measure again, confirm improvement, ensure tests still pass.

### Prohibition:
No premature micro-optimization ("premature optimization is the root of all evil").

---

## 7. Project Scaffold

**Trigger:** When a user requests creating a new project ("buat project X").

### Workflow:
1. **Follow the user's requested stack** (Laravel → Laravel, React → React).
   - Do not switch to a different stack without approval.
2. Check available tools first:
   ```bash
   which php composer node npm python3 pip3
   ```
   - If missing: inform user and suggest installation steps.
3. Scaffold using official tools (`composer create-project`, `npm create`, etc.).
4. Provide basic structure + minimal runnable files.
5. Verify: run a command that proves the project works (version, serve, test).

### Prohibition:
Do not offer alternative stack choices when the user has already specified one.

---

## 8. Python Modern

**Trigger:** When writing Python code — prefer modern, idiomatic, stdlib-first patterns.

### Standards:
- Prefer stdlib (`pathlib`, `dataclasses`, `functools`, `itertools`) over external libraries.
- Use type hints:
  ```python
  def function(param: int) -> str:
  ```
  Include: `from __future__ import annotations`
- Use `dataclass` for data structures, not fragile dicts.
- Use context managers (`with`) for resources (files, connections).
- Use f-strings for formatting; avoid chained concatenation.
- List/dict comprehensions when clear; don't force them.

### Prohibition:
Do not rewrite working code just to make it "more modern" (lazy rule applies).

---

## 9. Security

**Trigger:** When touching code that accepts or processes user input.

### Mandatory Checks:
1. **Injection** — never concatenate raw input into shell commands or SQL without escaping.
2. **Path traversal** — validate user paths (`../`), restrict to allowed directories.
3. **Secrets** — API keys/passwords must NOT be hardcoded or committed; use environment variables.
4. **Input validation** — validate type, length, range; never trust input.
5. **Error handling** — never expose internal details/tracebacks to users.

### Command Safety:
- Avoid `shell=True` with user input; use list arguments with `shlex` for sanitization.

---

## 10. TDD (Test-Driven Development)

**Trigger:** When implementing new features or code — always follow RED-GREEN-REFACTOR.

### Required Workflow:
1. **RED** — Write a failing test first (`tdd_status` / `run_tests` → RED).
2. **GREEN** — Write minimal implementation to pass the test.
3. **REFACTOR** — Clean up code without changing behavior; tests must stay green.

### Rules:
- Never implement before tests are written.
- Implement minimally: just enough to pass the test.
- Use `tdd_status` before and after edits to check RED/GREEN/NO_TESTS status.

---

*Exported from dhybrid-agent project skills directory.*