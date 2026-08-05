# dhybrid-agent — Quick Reference Card

## Commands

| Command | Description |
|---------|-------------|
| `dhybrid repl` | Start interactive REPL (default tanpa subcommand) |
| `dhybrid run "task"` | Run single task |
| `dhybrid tokens` | Token & cost dashboard |
| `dhybrid resume <session_id>` | Lanjutkan sesi lama |
| `dhybrid sessions` | Daftar sesi |
| `dhybrid skills` | Daftar skill |
| `dhybrid self-update` | Update to latest version |
| `dhybrid install` | Reinstall/update via installer |
| `dhybrid doctor` | Health check (config, key, koneksi, allowlist) |
| `dhybrid --model <preset>` | Set model utama dari preset |
| `dhybrid --cwd <dir>` | Kerjakan di direktori lain |
| `dhybrid --list-presets` | Cetak semua preset model |

## REPL Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl-R` | History search |
| `Tab` | Auto-complete commands/skills |
| `Ctrl-C` | Cancel current task |
| `Ctrl-D` | Exit |

## Slash Commands (in REPL)

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model <name>` | Switch model |
| `/key <provider> <value>` | Set API key |
| `/tokens` | Token usage dashboard |
| `/compact` | Compact context |
| `/sessions` | List sessions |
| `/skills` | List/enable skills |
| `/skill <name>` | Force skill |
| `/skill off` | Disable forced skill |
| `/clear` | Reset conversation |
| `/quit` | Exit |

## Skill References

| Syntax | Description |
|--------|-------------|
| `@skill-name` | Force inject skill |
| `/skill name` | Force skill for session |
| `/skill off` | Disable forced skill |

## Essential Tools

### File Operations
```bash
read_file          # Read file (path, limit, offset)
write_file         # Write file (path, content)
apply_patch        # Apply patch (path, old_string, new_string)
```

### Search
```bash
grep               # Search content (pattern, path, file_glob)
find_files         # Find files (pattern, path)
code_map           # AST-based code map
```

### Git
```bash
git_status         # Git status
git_diff           # Git diff
git_commit         # Git commit
git_log            # Git log
```

### Testing
```bash
run_tests          # Run tests (pytest, etc.)
tdd_status         # TDD status (RED/GREEN/REFACTOR)
```

### Language-Specific
```bash
# Go
go_test, go_vet, go_fmt, go_build, golangci_lint, gosec

# Rust
cargo_test, cargo_build, cargo_check, cargo_fmt, cargo_clippy, cargo_audit

# TypeScript/Node
npm_test, npm_build, tsc_check, eslint_check, jest_test, vitest_test, prettier_fmt

# Java
mvn_test, mvn_build, gradle_test, gradle_build, spotbugs_check, checkstyle_check

# C#
dotnet_test, dotnet_build, dotnet_restore, dotnet_fmt, dotnet_ef_migrations
```

### Advanced
```bash
orchestrator           # Multi-agent task
codegen_openapi        # OpenAPI → FastAPI
codegen_graphql        # GraphQL → Strawberry
codegen_protobuf       # Protobuf → gRPC
ci_cd                  # Generate CI/CD
episodic_remember      # Store memory
episodic_recall        # Search memory
semantic_search        # Vector code search
```

## Configuration Quick Access

Konfigurasi ada di `config/default.yaml` (atau `--config <path>`). Tidak ada
subcommand `dhybrid config` di versi ini — ubah via: file YAML, env var, atau
slash `/model`, `/key`, `/settings` saat REPL.

```bash
# Pilih model dari preset saat menjalankan
dhybrid --model anthropic-big repl
dhybrid --model gemini-fast repl

# Lihat preset yang tersedia
dhybrid --list-presets

# Path config custom
dhybrid --config ./produksi.yaml repl
```

## Environment Variables

```bash
# Model overrides
DHYBRID_MODEL=gpt-4o
DHYBRID_PROVIDER=openai
DHYBRID_BASE_URL=https://api.openai.com/v1
DHYBRID_SMALL_MODEL=gpt-4o-mini

# Feature flags
DHYBRID_NO_SKILL=1          # Disable auto-skill
DHYBRID_DEBUG=1             # Debug mode
DHYBRID_NO_TELEMETRY=1      # Disable telemetry
```

## Project Structure

```
project/
├── .dhybrid/              # Workspace (auto-created)
│   ├── skills/            # Auto-learned + manual skills
│   ├── memory.sqlite      # Long-term memory
│   ├── sessions.sqlite    # Session history
│   └── cache.sqlite       # Prompt cache
├── config/
│   └── default.yaml       # Project config
├── docs/                  # Documentation
└── src/                   # Source code
```

## Keyboard Shortcuts (REPL)

| Shortcut | Action |
|----------|--------|
| `↑` / `↓` | History navigation |
| `Ctrl-A` | Start of line |
| `Ctrl-E` | End of line |
| `Ctrl-K` | Kill to end |
| `Ctrl-U` | Kill to start |
| `Ctrl-W` | Kill word back |
| `Meta-B` | Word back |
| `Meta-F` | Word forward |

## Common Workflows

### 1. New Feature Development
```bash
dhybrid repl
> buat fitur authentication dengan JWT
# Agent: plans, writes code, runs tests, creates skill
```

### 2. Bug Fix
```bash
dhybrid run "perbaiki bug login: token expired tidak handle"
# Agent: reproduces, fixes, tests, verifies
```

### 3. Code Review
```bash
dhybrid run "review kode di src/auth untuk security issues"
# Agent: analyzes, reports vulnerabilities
```

### 4. Refactor
```bash
dhybrid run "refactor user service: extract repository pattern"
# Agent: plans, implements incrementally
```

### 5. Generate from Spec
```bash
dhybrid run "generate FastAPI dari openapi.yaml"
# Agent: uses codegen_openapi tool
```

## Troubleshooting Quick Fixes

| Problem | Fix |
|---------|-----|
| "Model not found" | Check `DHYBRID_MODEL` env or `/model` command |
| "Tool not allowed" | Add to `tool.allowlist` in config |
| "API key missing" | Set via `/key provider value` or env var |
| "Skills not loading" | Check `skills.auto_learn=true` |
| "Memory not persisting" | Same workspace dir, check `.dhybrid/memory.sqlite` |
| "Tests failing" | Run `dhybrid doctor` for health check |

## Useful Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias dr='dhybrid repl'
alias drun='dhybrid --cwd . run'   # alias run di folder saat ini
alias ddoc='dhybrid doctor'        # cek kesehatan
alias dsk='dhybrid skills'         # daftar skill
alias dre='dhybrid resume'         # lanjutkan sesi
```

## Links

- **Full Docs**: `docs/COMPLETE_GUIDE.md`
- **Getting Started**: `docs/GETTING_STARTED.md`
- **Advanced Usage**: `docs/ADVANCED_USAGE.md`
- **Multi-Language Guide**: `docs/MULTI_LANGUAGE_GUIDE.md`
- **Perpustakaan (lobi)**: `docs/README.md`