# dhybrid-agent — Complete Documentation

## Overview

**dhybrid-agent** is a powerful, token-efficient CLI coding agent built with a hybrid LLM routing architecture. It combines the best of both worlds: fast/cheap models for simple tasks and powerful models for complex reasoning — with automatic escalation when quality drops.

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
git clone https://github.com/your-org/dhybrid-agent
cd dhybrid-agent
pip install -e .

# Or install from pip
pip install dhybrid-agent
```

## Quick Start

```bash
# Start interactive REPL
dhybrid repl

# Run single task
dhybrid run "buat login page dengan test"

# Check configuration
dhybrid config show
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    dhybrid-agent                          │
├─────────────────────────────────────────────────────────┤
│  REPL / CLI                                              │
├─────────────────────────────────────────────────────────┤
│  Agent Loop (ReAct)                                     │
│  ├── Hybrid Router (quality-based escalation)           │
│  ├── Tool Registry (70+ tools)                          │
│  ├── Skills System (auto-learn + marketplace)           │
│  ├── Memory (episodic + vector search)                  │
│  └── Reasoning Traces / Self-Critique                   │
├─────────────────────────────────────────────────────────┤
│  Observability                                          │
│  ├── Prometheus Metrics (/metrics endpoint)             │
│  ├── OpenTelemetry Tracing (OTLP export)                │
│  └── Structured Logging                                 │
└─────────────────────────────────────────────────────────┘
```

## Configuration

### Config File Location
- Project: `config/default.yaml`
- User: `~/.dhybrid/config.yaml` (overrides project)
- Environment variables (highest priority)

### Key Sections

```yaml
# Model Configuration
model:
  provider: openai
  model: laguna-s-2.1-free
  base_url: https://opencode.ai/zen/v1
  api_key_env: OPENCODE_ZEN_API_KEY
  chain: ["bynara-big", "openrouter-big", "anthropic-big"]

# Budget Limits
budget:
  soft: 60000    # trigger compaction
  hard: 120000   # force stop

# Tool Settings
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
- `codegen_openapi` / `codegen_graphql` / `codegen_protobuf` — Generate code from specs
- `ci_cd` — Generate GitHub Actions / GitLab CI
- `episodic_remember` / `episodic_recall` — Persistent memory
- `semantic_search` — Vector-based code search

## Skills System

### Auto-Skill Learning
The agent automatically creates skills from successful sessions:

```bash
# User: "buat halaman login dengan validasi"
# Agent executes: terminal, write_file, run_tests
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

# Export skill to share
export_skill("~/.dhybrid/skills", "my-skill", "my-skill.json")

# Import skill
import_skill("~/.dhybrid/skills", "my-skill.json")

# Publish to marketplace
publish_skill("~/.dhybrid/skills", "my-skill", "~/marketplace")

# Install from marketplace
install_skill("~/.dhybrid/skills", "~/marketplace", "other-skill")
```

### Skill Composition
```python
from dhybrid.skills import compose_skills, Skill

workflow = compose_skills([
    Skill(name="setup", description="Setup project", body="..."),
    Skill(name="test", description="Run tests", body="..."),
    Skill(name="deploy", description="Deploy", body="..."),
], name="ci-workflow", description="Complete CI pipeline")

# Use composed skill
```

## Multi-Agent Orchestration

The orchestrator decomposes complex tasks into specialized subagents:

```bash
# User: "refactor authentication module"
# Agent creates: planner → executor → reviewer subagents
# Each with role-specific prompts
```

### Roles
- **Planner** — Breaks task into subtasks
- **Executor** — Implements each subtask
- **Reviewer** — Reviews code quality

## Code Generation

### From OpenAPI (FastAPI)
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

### From GraphQL (Strawberry)
```python
from dhybrid.tools.codegen import generate_from_graphql

schema = """
type User { id: ID!, name: String! }
type Query { users: [User!]! }
"""
code = generate_from_graphql(schema)
```

### From Protobuf (gRPC)
```python
from dhybrid.tools.codegen import generate_from_protobuf

proto = """
message User { int32 id = 1; string name = 2; }
service UserService { rpc GetUser(UserRequest) returns (User); }
"""
code = generate_from_protobuf(proto)
```

## Database Migrations

Auto-generate Alembic-compatible migrations:

```python
from dhybrid.tools.db_migrate import create_migration, generate_add_table_migration

# Create migration
migration = create_migration("add_users_table")

# Generate table migration
migration = generate_add_table_migration("users", [
    {"name": "id", "type": "INTEGER", "primary_key": True},
    {"name": "email", "type": "VARCHAR(255)", "unique": True},
    {"name": "created_at", "type": "TIMESTAMP", "default": "CURRENT_TIMESTAMP"}
])
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

# Start /metrics endpoint
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

# Initialize with OTLP endpoint
tracer = init_tracing(
    service_name="dhybrid-agent",
    otlp_endpoint="http://jaeger:4317"
)

# Use in code
with tracer.start_span("database.query") as span:
    span.set_attribute("query", "SELECT * FROM users")
```

### Grafana Dashboard
Import the pre-built dashboard from `docs/grafana-dashboard.json` for:
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

## Advanced Usage

### Custom Models
```bash
# Add custom model preset
dhybrid config preset add my-model \
  --provider openai \
  --model gpt-4o \
  --base-url https://api.openai.com/v1 \
  --api-key-env OPENAI_API_KEY
```

### Disable Features
```bash
# Disable auto-skill learning
dhybrid config set skills.auto_learn false

# Disable telemetry
DHYBRID_NO_TELEMETRY=1
```

### Debugging
```bash
# Enable debug output
DHYBRID_DEBUG=1 dhybrid repl

# View reasoning traces
# Available in LoopResult.reasoning_trace
```

## Troubleshooting

### Common Issues

**Model not found / 401 error**
```bash
# Check API key
echo $OPENAI_API_KEY
# Or set via config
dhybrid config set model.api_key_env MY_CUSTOM_KEY
```

**Tools not available**
```bash
# Check allowlist
dhybrid config show tool.allowlist
# Add missing tools
dhybrid config set tool.allowlist "[terminal, write_file, custom_tool]"
```

**Memory not persisting**
```bash
# Check workspace
dhybrid config show workspace
# Ensure same project directory
cd /your/project && dhybrid repl
```

**Episodic memory failing**
```bash
# Install sentence-transformers
pip install sentence-transformers
# Or use offline mode
```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing`
3. Write tests: `pytest tests/unit/ -x`
4. Run integration tests: `pytest tests/integration/ -x`
5. Submit PR

## License

MIT License — see LICENSE file for details.

## Support

- Documentation: https://dhybrid-agent.readthedocs.io
- Issues: https://github.com/your-org/dhybrid-agent/issues
- Discord: https://discord.gg/dhybrid