# dhybrid-agent — Complete Documentation

## Overview

**dhybrid-agent** adalah CLI coding agent berbasis Python, terkoordinasi levat routing LLM hybrid. Model kecil murah untuk task simpel, model besar untuk reasoning kompleks, dengan escalation otomatis saat kualitas output turun.

## Key Features

- **Hybrid Routing** — Automatic model escalation based on quality scoring
- **Multi-Language Support** — Go, Rust, TypeScript, Java, C#, Python, JavaScript
- **Persistent Memory** — Episodic memory with vector search across sessions
- **Auto-Skill Learning** — Learns from successful sessions automatically
- **Skill Marketplace** — Import/export/share reusable skills
- **Skill Composition** — Combine skills into complex workflows
- **Production Observability** — Prometheus metrics, OpenTelemetry tracing
- **CI/CD Integration** — Generate GitHub Actions, GitLab CI configs
- **Code Generation** — From OpenAPI, GraphQL, Protobuf specs
- **Database Migrations** — Auto-generate Alembic-compatible migrations

## Installation

```bash
# Clone and setup
git clone https://github.com/FerzDevZ/dhybrid-agent
cd dhybrid-agent
pip install -e .

# Atau via installer resmi
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash
```

## Quick Start

```bash
# Start interactive REPL
dhybrid repl

# Run single task
dhybrid run "buat login page dengan test"

# Check health & config
dhybrid doctor
```

## Architecture

```
CLI / REPL
└── Agent Loop (ReAct)
    ├── Hybrid Router (quality-based escalation)
    ├── Tool Registry (70+ tools)
    ├── Skills Engine (auto-learn + marketplace)
    ├── Memory (episodic + vector search)
    └── Reasoning Traces / Self-Critique

Observability
├── Prometheus Metrics (/metrics endpoint)
├── OpenTelemetry Tracing (OTLP export)
└── Structured Logging
```

## Configuration

### Structured Location

- Project: `config/default.yaml`
- User: `~/.dhybrid/config.yaml` (overrides project)
- Environment variables (highest priority)

### Key Sections

```yaml
# Model Configuration
model:
  provider: openai
  model: gpt-4o
  base_url: https://api.openai.com/v1
  api_key_env: OPENAI_API_KEY
  chain:
    - bynara-big      # First escalation
    - openrouter-big  # Second escalation
    - anthropic-big   # Final escalation

# Budget
budget:
  soft: 60000    # trigger compaction
  hard: 120000   # hard stop

# Tools
tool:
  max_output_chars: 8000
  allowlist: [terminal, write_file, go_test, cargo_test, ...]

# Skills
skills:
  auto_learn: true
  max_inject: 3
  max_chars: 800
  fallback: general
```

### Environment Variables

```bash
# Model overrides
DHYBRID_MODEL=gpt-4o
DHYBRID_PROVIDER=openai
DHYBRID_BASE_URL=https://api.openai.com/v1
DHYBRID_SMALL_MODEL=gpt-4o-mini

# Disable auto-skill
DHYBRID_NO_SKILL=1

# Debug mode
DHYBRID_DEBUG=1
```

## Available Tools

### Core Tools

- `terminal` — Execute shell commands
- `read_file` / `write_file` / `apply_patch` — File operations
- `grep` / `find_files` — Search
- `git_*` — Git operations
- `run_tests` — Run tests (pytest, etc.)

### Language-Specific Tools

**Go** (7 tools)

```bash
go_test, go_vet, go_fmt, go_build, go_mod_tidy, golangci_lint, gosec
```

**Rust** (8 tools)

```bash
cargo_test, cargo_build, cargo_check, cargo_fmt,
cargo_clippy, cargo_audit, cargo_update, cargo_outdated
```

**TypeScript/Node** (9 tools)

```bash
npm_test, npm_build, npm_install, npm_audit,
tsc_check, eslint_check, jest_test, vitest_test, prettier_fmt
```

**Java/Maven/Gradle** (10 tools)

```bash
mvn_test, mvn_build, mvn_compile, mvn_package, mvn_clean,
gradle_test, gradle_build, gradle_check, spotbugs_check, checkstyle_check
```

**C#/.NET** (9 tools)

```bash
dotnet_test, dotnet_build, dotnet_restore, dotnet_clean,
dotnet_fmt, dotnet_format, dotnet_tool_install, dotnet_outdated, dotnet_ef_migrations
```

### Advanced Tools

- `orchestrator` — Multi-agent task orchestration
- `codegen_openapi` / `codegen_graphql` / `codegen_protobuf` — Generate code dari spec
- `ci_cd` — Generate GitHub Actions / GitLab CI
- `episodic_remember` / `episodic_recall` — Persistent memory
- `semantic_search` — Vector-based code search
- `tdd_status` — TDD status (RED/GREEN/REFACTOR)

## Skills System

### Auto-Skill Learning

Sistem otomatis membuat skill dari sesi yang sukses:

```bash
# User: "buat halaman login yang valid"
# Agent executes: write_file, run_tests
# Result: Creates skill "buat-halaman-login"
```

### Manual Skill Creation

```markdown
# ~/.dhybrid/skills/my-skill/SKILL.md
---
name: my-skill
description: Custom skill for my workflow
---
# my-skill

**Steps:**
1. Run tests
2. Build project
3. Deploy
```

### Skill Marketplace

```python
from dhybrid.skills import export_skill, import_skill, publish_skill, install_skill

# Make skill shareable
export_skill("~/.dhybrid/skills", "my-skill", "my-skill.json")

# Import skill
import_skill("~/.dhybrid/skills", "my-skill.json")

# Publish ke marketplace
publish_skill("~/.dhybrid/skills", "my-skill", "~/marketplace")

# Install dari marketplace
install_skill("~/.dhybrid/skills", "~/marketplace", "other-skill")
```

### Skill Composition

```python
from dhybrid.skills import compose_skills, Skill

workflow = compose_skills([
    Skill(name="setup", description="Setup project", body="..."),
    Skill(name="test", description="Jalankan test", body="..."),
    Skill(name="deploy", description="Deploy", body="..."),
], name="ci-workflow", description="Complete CI pipeline")
```

## Multi-Agent Orchestration

Orchestrator memecah task kompleks menjadi subagent khusus:

```bash
# User: "refactor authentication module"
# Agent creates: planner → executer → reviewer subagents
```

### Roles

- **Planner** — Memecah task jadi subtask
- **Executor** — Mengimplementasi tiap subtask
- **Reviewer** — Menilai kualitas code

## Code Generation

### OpenAPI → FastAPI

```python
from dhybrid.tools.codegen import generate_from_openapi

spec = {
    "openapi": "3.0.0",
    "paths": {
        "/users": {
            "get": {"summary": "List users"},
            "post": {"summary": "Create user"}
        }
    }
}
code = generate_from_openapi(spec, framework="fastapi")
```

### GraphQL → Strawberry

```python
from dhybrid.tools.codegen import generate_from_graphql

schema = """
type User { id: ID!, name: String! }
type Query { users: [User!]! }
"""
code = generate_from_graphql(schema)
```

### Protobuf → gRPC

```python
from dhybrid.tools.codegen import generate_from_protobuf

proto = """
message User { int32 id = 1; string name = 2; }
service UserService { rpc GetUser(UserRequest) returns (User); }
"""
code = generate_from_protobuf(proto)
```

## Database Migrations

Auto-generate migration kompatibel Alembic:

```python
from dhybrid.tools.db_migrate import create_migration, generate_add_table_migration

# Create migration
migration = create_migration("add_users_table")

# Generate table migration
migration = create_migration_(
  "users",
  [
    {"name": "id", "type": "INTEGER", "primary_key": True},
    {"name": "email", "type": "VARCHAR(255)", "unique": True},
    {"name": "created_at", "type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
  ]
)
```

## CI/CD Generation

Generate pipeline configs:

```python
from dhybrid.tools.ci_cd import generate_github_actions, generate_gitlab_ci

# GitHub Actions
workflow = generate_github_actions(
    language="python",
    test_cmd="pytest",
    lint_cmd="ruff check .",
    build_cmd="pip install -e ."
)

# GitLab CI
gitlab_ci = generate_gitlab_ci(
    language="rust",
    test_cmd="cargo test",
    build_cmd="cargo build --release"
)
```

## Observability

### Prometheus Metrics

```python
from dhybrid.efficiency.prometheus_exporter import start_metrics_server

# Expose /metrics
server = start_metrics_server(port=9090)
```

**Available Metrics:**

- `dhybrid_tokens_used_total` — Total tokens consumed
- `dhybrid_quality_score` — Output quality (0-100)
- `dhybrid_tool_calls_total` — Tool invocation count
- `dhybrid_escalations_total` — Model escalation count
- `dhybrid_session_duration_seconds` — Session duration

### OpenTelemetry Tracing

```python
from dhybrid.efficiency.tracing import init_tracing

# Inisialisasi dengan OTLP endpoint
tracer = init_tracing(
    service_name="dhybrid-agent",
    otlp_endpoint="http://jaeger:4317"
)

# Usage:
with tracer.start_span("database.query") as span:
    span.set_attribute("query", "SELECT * FROM users")
```

### Grafana Dashboard

Import predefined dashboard dari `docs/grafana-dashboard.json` untuk:

- Token usage trends
- Quality score distribution
- Tool usage heatmap
- Escalation frequency
- Session duration percentiles

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .
ENTRYPOINT ["dhybrid"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dhybrid-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent
        image: dhybrid-agent:latest
        env:
        - name: DHYBRID_MODEL
          value: "gpt-4o"
        - name: DHYBRID_PROVIDER
          value: "openai"
```

### Systemd Service

```ini
[Unit]
Description=dhybrid-agent
After=network.target

[Service]
Type=simple
User=dhybrid
WorkingDirectory=/opt/dhybrid-agent
ExecStart=/opt/dhybrid-agent/.venv/bin/dhybrid repl
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Tips

### Custom Models

```bash
# Pilih preset saat menjalankan (tanpa perlu config)
dhybrid --model anthropic-big repl
dhybrid --model gemini-fast repl
dhybrid --list-presets            # semua preset

# Atau set model dari dalam REPL
#   /model <nama>   → ganti model utama
#   /settings       → pilih/input provider manual
```

### Disable

```bash
# Disable auto-skill learning (via env var, atau config skills.auto_learn=false)
DHYBRID_NO_SKILL=1

# Disable telemetry
DHYBRID_NO_TELEMETRY=1
```

### Debug

```bash
# Debug output on
DHYBRID_DEBUG=1 dhybrid repl

# Reasoning trace
# Tersedia di LoopResult.reasoning_trace
```

## Troubleshooting

### Common Issues

**Model tidak ditemukan / 401**

```bash
# Check API key
echo $OPENAI_API_KEY
# /key saat REPL, atau env var; atau ganti provider: /model <nama>
```

**Tools tidak tersedia**

```bash
# Health check
dhybrid doctor
# Tambah tool ke tool.allowlist di config/default.yaml
# (regenerate auto saat restart; pastikan tool terdaftar di registry)
```

**Memory tidak persisten**

```bash
# Gunakan direktori proyek yang sama
cd /your/project && dhybrid repl
# Data tersimpan di workspace .dhybrid/ proyek tsb (memory.sqlite, sessions.sqlite)
```

**Episodic memory error / tidak bekerja**

```bash
# Install sentence-transformers
pip install sentence-transformers
# Atau pakai offline mode
```

## Contributing

1. Fork repository
2. Buat branch pipit: `git checkout -b feature/amazing`
3. Tulis test: `pytest tests/unit/ -x`
4. Jalankan integrasi: `pytest tests/integration/ -x`
5. Kirim PR

## License

MIT License — lihat LICENSE file untuk detail.

## Support

- GitHub Issues: https://github.com/FerzDevZ/dhybrid-agent/issues