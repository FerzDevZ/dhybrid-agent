# dhybrid-agent — Advanced Usage Guide

## Custom Skills Development

### Skill Structure

```
~/.dhybrid/skills/your-skill/
├── SKILL.md           # Required: main skill definition
├── scripts/           # Optional: helper scripts
├── templates/         # Optional: code templates
└── assets/            # Optional: images, data files
```

### SKILL.md Format

```markdown
---
name: your-skill-name
description: Human-readable description for skill selection
version: 1.0.0
tags: [category, subcategory]
author: your-name
---

# Your Skill Name

**Tujuan:** What this skill accomplishes in one sentence.

## Kapan Digunakan
- Scenario 1
- Scenario 2

## Prasyarat
- Tool/dependency requirements
- Project structure assumptions

## Langkah-Langkah

### 1. Preparation
```bash
# Commands to run
```

### 2. Implementation
```python
# Code patterns
```

### 3. Verification
```bash
# Test commands
```

## Variasi
- **Variation A:** When condition X
- **Variation B:** When condition Y

## Troubleshooting
| Error | Solution |
|-------|----------|
| Common error | Fix |

## Referensi
- Link to docs
- Related skills
```

### Skill with Parameters

Untuk skill yang menerima parameter, dokumentasikan di frontmatter:

```markdown
---
name: deploy-service
description: Deploy a service to Kubernetes
params:
  - name: service_name
    type: string
    required: true
    description: Name of the service
  - name: namespace
    type: string
    required: false
    default: "default"
    description: Kubernetes namespace
---
```

## Auto-Skill Customization

### Disable Auto-Learn untuk Task Spesifik

```python
# Di dalam konteks sesi
ctx.cfg.skills["auto_learn"] = False
# Atau via env
# DHYBRID_NO_SKILL=1
```

### Custom Skill Naming

```python
from dhybrid.skills.loader import slugify

# Override naming untuk pattern tertentu
def custom_slugify(goal: str) -> str:
    if "deploy" in goal.lower():
        return f"deploy-{slugify(goal)}"
    return slugify(goal)
```

### Skill Templates

Buat template reuse di `~/.dhybrid/skills/templates/`:

```
templates/
├── api_endpoint.py      # FastAPI endpoint template
├── react_component.tsx  # React component template
├── k8s_deployment.yaml  # K8s deploy template
└── dockerfile           # Multi-stage Dockerfile
```

Referensi di skill:

```markdown
**Template:** `templates/api_endpoint.py`
```

## Advanced Memory Usage

### Episodic Memory Queries

```python
# Cari dengan filter spesifik
from dhybrid.session.episodic_memory import EpisodicMemory

memory = EpisodicMemory(db_path)
results = memory.search(
    query="authentication bug fix",
    limit=10,
    min_score=0.7
)
```

### Memory Namespaces

```python
# Pisahkan memori per project/team
project_memory = MemoryStore(
    Path.home() / ".dhybrid" / "projects" / "my-project" / "memory.sqlite"
)
team_memory = MemoryStore(
    Path.home() / ".dhybrid" / "teams" / "backend" / "memory.sqlite"
)
```

### Memory Retention Policies

```yaml
# Di config
memory:
  retention_days: 90
  max_entries: 10000
  auto_attend: true
```

## Custom Tool Development

### Tool Structure

```python
# dhybrid/tools/my_tool.py
from dhybrid.tools.registry import ToolRegistry

def my_custom_tool(workspace: str, param: str) -> str:
    """Description of what the tool does."""
    # Implementation
    return "Result"

def register(reg: ToolRegistry, max_chars: int = 8000):
    reg.register(
        "my_tool",
        "Description for the agent",
        {
            "workspace": {"type": "string", "required": True},
            "param": {"type": "string", "required": True}
        },
        my_custom_tool
    )
```

### Register Custom Tool

```python
# Di dhybrid/tools/__init__.py
from dhybrid.tools import my_tool

def build_tools(cfg, ...):
    # ... existing code
    my_tool.register(reg, max_chars=max_chars)
```

### Tool dengan External Dependencies

```python
def external_api_tool(endpoint: str, api_key: str = "") -> str:
    """Call external API."""
    import os

    key = api_key or os.environ.get("MY_API_KEY")
    if not key:
        return "ERROR: API key required"

    import requests
    resp = requests.get(endpoint, headers={"Authorization": f"Bearer {key}"})
    return resp.text
```

## Workflow Automation

### Pre-commit Hooks

```bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: dhybrid-check
        name: dhybrid quality check
        entry: dhybrid run "review staged changes for quality issues"
        language: system
        types: [python, javascript, typescript]
```

### CI Integration

```yaml
# .github/workflows/dhybrid-review.yml
name: dhybrid Code Review
on: [pull_request]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run dhybrid review
        run: |
          pip install dhybrid-agent
          dhybrid run "review PR changes for bugs, security, performance" \
            --context "${{ github.event.pull_request.body }}"
```

### Scheduled Tasks

```python
# cron job untuk daily code quality
from dhybrid.cron import create_daily_review

create_daily_review(
    time="02:00",
    prompt="analyze codebase for technical debt and security issues",
    workspace="/path/to/project"
)
```

## Performance Optimization

### Token Budget Tuning

```yaml
# Compact lebih agresif untuk hemat biaya
budget:
  soft: 30000    # Compact earlier
  hard: 60000    # Hard stop sooner

# Atau longgar demi kualitas
budget:
  soft: 100000
  hard: 200000
```

### Context Management

```yaml
context:
  keep_recent: 6      # Fewer recent messages
  compact_ratio: 0.3  # More aggressive compaction
```

### Skill Injection Limits

```yaml
skills:
  max_inject: 2       # Fewer skills = fewer tokens
  max_chars: 500      # Buffer skill bodies
```

### Model Selection Strategy

```yaml
# Pakai model murah untuk kebanyakan task
model:
  provider: openai
  model: gpt-4o-mini
  chain:
    - bynara-big      # First escalation
    - openrouter-big  # Second escalation
    - anthropic-big   # Final escalation
```

## Security Foundation

### Allowlist Only

```yaml
tool:
  allowlist: [terminal, read_file, write_file, git_status]
  # No shell, no network tools unless explicitly needed
```

### Confirmation Required

```bash
# Interactive mode (default) - confirm dangerous commands
dhybrid repl

# Non-interactive - auto-confirm (switching Q: apakah aman?)
dhybrid repl --yes
```

### Workspace Isolation

```yaml
# Batasi ke direktori project saja
workspace: ./project
# Agent tidak bisa until di luar folder
```

## Debugging & Profiling

### Debug Mode

```bash
# Full debug output
DHYBRID_DEBUG=1 dhybrid repl

# Debug spesific component
DHYBRID_DEBUG=tools dhybrid repl
DHYBRID_DEBUG=skills dhybrid repl
```

### Profiling

```python
# Profil agent loop
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run agent
result = loop.run(prompt)

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(20)
```

### Token Usage Analysis

```bash
# Lihat breakdown token
dhybrid run "analyze token usage for last 10 sessions" --format json
```

## Integration Patterns

### VS Code Extension

```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "dhybrid: Run Task",
      "type": "shell",
      "command": "dhybrid run \"${input:task}\"",
      "problemMatcher": []
    }
  ],
  "inputs": [
    {
      "id": "task",
      "type": "promptString",
      "description": "Task for dhybrid"
    }
  ]
}
```

### LSP Integration

```python
# Custom LSP integration
from dhybrid.tools import semantic_search

def lsp_completion(document, position):
    query = document.text[:position.character]
    results = semantic_search(query, workspace="/project")
    return format_completions(results)
```

### Webhook Integration

```python
# Slack/Discord notifications
from dhybrid.hooks import SlackHook

hooks = SlackHook(
    webhook_url="https://hooks.slack.com/...",
    channel="#dhybrid-logs",
    events=["task_complete", "error", "escalation"]
)
```

## Extending the Agent

### Custom Model Provider

```python
# dhybrid/llm/providers/custom.py
from dhybrid.llm.base import BaseProvider, ChatMessage

class CustomProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)

    async def chat(self, messages, **kwargs):
        # Custom API call
        return response
```

Register di `dhybrid/llm/registry.py`.

### Custom Quality Scorer

```python
# dhybrid/agent/quality.py
def custom_quality_score(text: str, context: dict) -> int:
    """Score 0-100 berdasarkan kriteria custom."""
    score = 100

    # Penalty TODO/FIXME
    if "TODO" in text or "FIXME" in text:
        score -= 10

    # Reward tests
    if "def test_" in text:
        score += 5

    return max(0, min(100, score))
```

### Custom Hooks

```python
# dhybrid/agent/hooks.py
class CustomHook:
    def on_step(self, step, model, usage, budget):
        # Log to custom system
        pass

    def on_tool_call(self, tool, args, result):
        # Audit trail
        pass

    def on_escalation(self, from_model, to_model, reason):
        # Alert on escalation
        pass
```

## Best Practices

### 1. Jaga Skill Fokus
- Satu skill = satu workflow jelas
- Komposisi workflow kompleks dari skill sederhana

### 2. Version Skills Anda

```markdown
---
name: my-skill
version: 1.2.0
---
```

### 3. Dokumentasi Edge Cases

- Apa yang terjadi ketika dependency hilang?
- Bagaimana handle partial failure?

### 4. Test Skills Anda

```bash
# Test skill terisolasi
dhybrid run "gunakan skill my-skill untuk deploy staging"
```

### 5. Share via Marketplace

```bash
# Export
dhybrid skill export my-skill my-skill.json

# Team imports
dhybrid skill import my-skill.json
```

## Migration Guide

### Dari v0.8 ke v0.9+

Perubahan kunci:

- `skills.auto_learn` kini default `true`
- Modul `episodic_memory` baru (opsional)
- `tool.allowlist` wajib untuk tool baru
- Config mendukung field default `extra` untuk custom

```bash
# Langkah migrasi
dhybrid self-update       # 1. update tool
dhybrid doctor            # 2. cek kesehatan
config: tambahkan        # 3. update config Anda
```

## Resources

- **Source Code:** `src/dhybrid/`
- **Config Schema:** `config/default.yaml`
- **Skill Examples:** `~/.dhybrid/skills/`
- **Test Suite:** `tests/unit/`, `tests/integration/`