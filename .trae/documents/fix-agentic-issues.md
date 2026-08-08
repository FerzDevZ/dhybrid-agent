# Plan: Fix Agentic AI Issues Based on User Terminal Output

## Summary
User reported multiple issues when running `dhybrid` in their project:
1. **Wrong path resolution** - Agent tried to read `/home/firman/ayam/app.py` but Flask project is in `/home/firman/ayam/flask-login/`
2. **Garbled streaming output** - Character-by-character fragmentation like "H\nai!👋" 
3. **Wrong STUCK label** - Task succeeded but labeled STUCK
4. **Clarify not working** - Agent didn't ask for clarification on ambiguous prompts
5. **Installer not interactive** - No prompt to run after install

---

## Current State Analysis

### Project Structure (from investigation)
```
/home/firman/ayam/                    ← User runs `dhybrid` here (cwd)
├── app.py (does NOT exist)
└── flask-login/                      ← Actual Flask project
    ├── app.py                        ← Real entry point
    ├── requirements.txt
    └── templates/
        ├── base.html
        ├── login.html
        ├── register.html
        └── dashboard.html
```

### Root Cause of Path Issue
- User runs `dhybrid` from `/home/firman/ayam/` 
- Agent's cwd = `/home/firman/ayam/`
- Agent tries to read `app.py` (relative to cwd) → fails
- Actual project is in subdirectory `flask-login/`
- The security boundary (`check_path_safe`) uses `Path.cwd().resolve()` as base

### Architecture (from exploration)
- **cwd normalization**: `Path(args.cwd or ".").expanduser().resolve()` in `cli.py:24`
- **Security boundary**: `tools/security.py` uses `Path.cwd().resolve()` as allowed base
- **Project detection**: Hash of resolved cwd for memory/skills isolation
- **Auto-resume**: Per-cwd session tracking in SQLite

---

## Proposed Changes

### 1. Fix Path Resolution - Add Project Auto-Detection
**File**: `src/dhybrid/session/context.py`  
**What**: Detect common project markers (package.json, Cargo.toml, go.mod, requirements.txt, pyproject.toml, .git) in cwd and subdirectories, suggest or auto-switch cwd  
**Why**: Agent should find the actual project root, not just use shell cwd

```python
# In SessionContext.__init__, after cwd is set:
def _detect_project_root(self, cwd: str) -> str:
    """Detect project root by looking for markers in cwd and parents."""
    markers = [
        "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",  # Python
        "package.json", "pnpm-lock.yaml", "yarn.lock",  # Node
        "Cargo.toml", "go.mod", "pom.xml", "build.gradle",  # Rust/Go/Java
        "composer.json", ".git",  # PHP/Git
    ]
    p = Path(cwd).resolve()
    for parent in [p] + list(p.parents):
        for marker in markers:
            if (parent / marker).exists():
                return str(parent)
    return cwd  # fallback
```

### 2. Fix Streaming Output - ToolBlockFilter Buffering
**File**: `src/dhybrid/agent/streaming.py`  
**What**: Already fixed in commit `022a545` - Added `_FLUSH_THRESHOLD = 256` and newline-based flushing  
**Status**: ✅ Done, needs verification

### 3. Fix STUCK Label - Extended Completion Detection
**File**: `src/dhybrid/efficiency/lazy.py`  
**What**: Already fixed in commit `b8a080c` - Extended `needs_change_check()` to recognize more phrases  
**Status**: ✅ Done, needs verification

### 4. Fix Clarify Behavior - Integration Check
**Files**: `src/dhybrid/agent/intent.py`, `src/dhybrid/ui/repl.py`  
**What**: Verify `detect_ambiguity()` is called in `_run_one()` before `run_agent()`  
**Why**: User reported agent didn't ask for clarification on ambiguous prompts

### 5. Fix Installer Interactivity
**File**: `install.sh`  
**What**: Already fixed in commit `3facd09` - Uses `/dev/tty` for prompt when piped  
**Status**: ✅ Done

---

## Assumptions & Decisions

| Decision | Rationale |
|----------|-----------|
| Auto-detect project root in subdirectory | Many projects have nested structure (monorepo, frontend/backend) |
| Don't auto-change cwd without confirmation | Could break user's mental model; suggest instead |
| Keep security boundary at detected project root | Prevents path traversal outside actual project |
| Priority: explicit `--cwd` > auto-detected > shell cwd | User intent > heuristic > default |

---

## Verification Steps

1. **Test project detection**:
   ```bash
   cd /home/firman/ayam && dhybrid run "list files"
   # Should detect flask-login/ and suggest/auto-switch
   ```

2. **Test streaming**:
   ```bash
   dhybrid run "hello world"
   # Output should be clean, not fragmented
   ```

3. **Test STUCK/DONE label**:
   ```bash
   dhybrid run "create a simple python file"
   # Should show DONE not STUCK when complete
   ```

4. **Test clarify**:
   ```bash
   dhybrid run "buat web login register"
   # Should show numbered options for stack selection
   ```

5. **Test installer**:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
   # Should prompt "Mau coba dhybrid sekarang? (Y/n)"
   ```

---

## Implementation Order

1. **Phase 1**: Add project auto-detection in `SessionContext.__init__` (high impact)
2. **Phase 2**: Verify streaming fix works with real model output
3. **Phase 3**: Verify STUCK label fix with real completion
4. **Phase 4**: Verify clarify integration in repl.py
5. **Phase 5**: Test installer end-to-end