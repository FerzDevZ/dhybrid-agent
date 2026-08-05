# dhybrid-agent — Quick Reference Card

## Commands

| Command | Description |
|---------|-------------|
| `dhybrid repl` | Start interactive REPL |
| `dhybrid run "task"` | Run single task |
| `dhybrid config show` | Show current config |
| `dhybrid config set key value` | Set config value |
| `dhybrid config preset add name` | Add model preset |
| `dhybrid self-update` | Update to latest version |
| `dhybrid doctor` | Health check |

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

```bash
# Show all config
dhybrid config show

# Get nested value
dhybrid config get model.provider

# Set value
dhybrid config set model.temperature 0.5
dhybrid config set skills.auto_learn false

# Manage presets
dhybrid config preset list
dhybrid config preset add my-model --provider openai --model gpt-4o
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
alias drun='dhybrid run'
alias dc='dhybrid config'
alias dcu='dhybrid self-update'
```

## Links

- **Full Docs**: `docs/COMPLETE_GUIDE.md`
- **Advanced Usage**: `docs/ADVANCED_USAGE.md`
- **Multi-Language Guide**: `docs/MULTI_LANGUAGE_GUIDE.md`
- **Deployment Guide**: `docs/DEPLOYMENT_GUIDE.md`