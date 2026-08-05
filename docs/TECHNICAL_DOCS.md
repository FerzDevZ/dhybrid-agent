# dhybrid-agent — Complete Technical Documentation

> **Version:** 0.9.6+ | **Last Updated:** 2025-08-05 | **Status:** Production Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Modules](#core-modules)
3. [Agent Loop](#agent-loop)
4. [Hybrid Routing](#hybrid-routing)
5. [Tools System](#tools-system)
6. [Skills System](#skills-system)
7. [Memory & Context](#memory--context)
8. [Multi-Language Support](#multi-language-support)
9. [Observability](#observability)
10. [Configuration](#configuration)
11. [CLI Interface](#cli-interface)
12. [Testing](#testing)
13. [Deployment](#deployment)
14. [Extending the Agent](#extending-the-agent)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        dhybrid-agent                             │
├─────────────────────────────────────────────────────────────────┤
│  CLI / REPL Interface                                           │
│  ├── Interactive mode (prompt_toolkit + rich)                   │
│  ├── Non-interactive mode (scripting/CI)                        │
│  └── Commands: repl, run, tokens, resume, sessions, skills,     │
│      doctor, self-update, install                                │
├─────────────────────────────────────────────────────────────────┤
│  SessionContext (Central Hub)                                    │
│  ├── Config (model, budget, tools, skills, presets)             │
│  ├── SessionStore (SQLite: sessions, messages, summaries)       │
│  ├── TokenBudget (soft/hard limits, compaction)                 │
│  ├── ContextManager (compaction, caching, keep_recent)          │
│  ├── ModelRegistry (multi-provider, cost tracking)              │
│  ├── HybridRouter (small/big model escalation)                  │
│  ├── MemoryStore (KV + FTS5 full-text search)                   │
│  ├── EpisodicMemory (SQLite + vector embeddings)                │
│  ├── ToolRegistry (70+ tools, allowlist, validation)            │
│  └── Skills Loader (auto-inject, marketplace, composition)      │
├─────────────────────────────────────────────────────────────────┤
│  Agent Loop (ReAct Pattern)                                     │
│  ├── Step: Model call → Tool execution → Verification           │
│  ├── Hybrid Routing (small → big model escalation)              │
│  ├── Quality Scoring (files, tests, mutating tools)             │
│  ├── Early Stop Detection (STUCK vs DONE)                       │
│  ├── Auto-skill Learning (from successful sessions)             │
│  ├── Clarify/Ask User Integration                               │
│  └── Reasoning Traces (Chain-of-Thought logging)                │
├─────────────────────────────────────────────────────────────────┤
│  Tools (70+)                                                    │
│  ├── Core: terminal, files, git, search, web                    │
│  ├── Code: code_map, dep_graph, semantic_search                 │
│  ├── Language Toolchains: Go, Rust, TypeScript, Java, C#        │
│  ├── Codegen: OpenAPI, GraphQL, Protobuf                        │
│  ├── CI/CD: GitHub Actions, GitLab CI                           │
│  ├── Database: Migrations (Alembic-compatible)                  │
│  ├── Memory: episodic_remember/recall/search                    │
│  ├── Orchestrator: Multi-agent planner/executor/reviewer        │
│  └── Config: Prometheus, OpenTelemetry, CI/CD                   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Token Efficiency** | 12 techniques: lazy policies, compaction, prompt caching, diff-based edits, semantic cache, early-stop, hybrid routing |
| **Local-First** | All data in `~/.dhybrid/` (SQLite, cache, skills, memory) — no telemetry |
| **Hybrid Routing** | Cheap model for mechanics → Quality escalation to powerful model |
| **Skill-Driven** | Auto-inject relevant skills via keyword/semantic matching |
| **Persistent Memory** | Episodic (cross-session) + Project KV + Semantic vector search |
| **Multi-Language** | Native toolchains for 6 languages with CI/CD generation |

---

## Core Modules

### 1. Configuration (`src/dhybrid/config.py`)

```python
@dataclass
class ModelConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.2
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    chain: list = field(default_factory=list)  # escalation chain

@dataclass
class Config:
    workspace: Path = Path.home() / ".dhybrid"
    model: ModelConfig = field(default_factory=ModelConfig)
    budget: dict = {"soft": 60000, "hard": 120000}
    context: dict = {"keep_recent": 8, "compact_ratio": 0.5}
    tool: dict = {"max_output_chars": 8000, "allowlist": [...]}
    skills: dict = {"auto_learn": True, "max_inject": 3, "max_chars": 800, "fallback": "general"}
    presets: dict = {}  # model presets
```

**Key Features:**
- `get(key)` / `set(key, value)` with dot notation: `cfg.get("model.temperature")`
- `extra` field for custom user settings
- Preset management: `get_preset()`, `list_presets()`, `add_preset()`
- YAML persistence: `load_config()`, `save_config()`
- Env overrides: `DHYBRID_MODEL`, `DHYBRID_PROVIDER`, `DHYBRID_BASE_URL`, `DHYBRID_SMALL_MODEL`

### 2. Token Budget (`src/dhybrid/efficiency/budget.py`)

```python
class TokenBudget:
    def __init__(self, soft: int = 60000, hard: int = 120000):
        self.soft = soft      # trigger compaction
        self.hard = hard      # force stop/compact
        self.used = 0
    
    def add(self, prompt: int, completion: int, cached: int = 0, tag: str = ""):
        self.used += prompt + completion
    
    @property
    def should_compact(self) -> bool:
        return self.used >= self.soft
    
    @property
    def exhausted(self) -> bool:
        return self.used >= self.hard
```

### 3. Context Management (`src/dhybrid/efficiency/context.py`)

```python
class ContextManager:
    def __init__(self, keep_recent: int = 8):
        self.keep_recent = keep_recent
        self.messages: list[ChatMessage] = []
        self.summary = ""
    
    def push(self, msg: ChatMessage):
        self.messages.append(msg)
    
    def compact(self, tokenizer, budget: TokenBudget) -> bool:
        # Compacts old messages, keeps recent + summary
        pass
```

### 4. Prompt Cache (`src/dhybrid/efficiency/cache.py`)

- SQLite-based prompt/response caching
- Anthropic `cache_control` header support
- Key: `model + messages + params` hash

---

## Agent Loop

### Main Loop (`src/dhybrid/agent/loop.py`)

```python
class AgentLoop:
    def run(self, user_prompt: str, system_prompt: str, push_prompt: bool = True) -> LoopResult:
        # 1. Build messages (system + context + skills + user prompt)
        # 2. For each step (up to max_steps):
        #    a. Check budget → compact if needed
        #    b. Call model (with escalation chain)
        #    c. Execute tool calls (parallel where possible)
        #    c. Live verify: check file changes every 2 steps
        #    d. Early stop detection:
        #       - Quality score threshold
        #       - Evidence of work (files, tests, mutating tools)
        #       - Intent without execution detection
        #       - Silent model nudging
        #    e. Escalation: quality threshold → escalate to bigger model
        #    f. Clarify/Ask user detection → pause loop
        # 3. Finalize: quality score, files created, tests passed
```

### LoopResult

```python
@dataclass
class LoopResult:
    final_text: str = ""
    steps: int = 0
    compacted: bool = False
    stopped_early: bool = False
    escalated: bool = False
    escalation_count: int = 0
    budget_exhausted: bool = False
    files_created: int = 0
    tests_passed: bool | None = None
    quality_score: int = 0
    escalated_quality: bool = False
    escalation_count: int = 0
    pending_question: dict | None = None  # ask_user/clarify
    reasoning_trace: ReasoningTrace = None  # Chain-of-Thought log
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Routing** | Small model for mechanics → escalate to big model on quality drop |
| **Quality Scoring** | 0-100 based on files created, tests, mutating tools, completeness |
| **Early Stop** | STUCK (no evidence) vs DONE (evidence present) |
| **Escalation** | Auto-escalate to bigger model on quality drop or build questions |
| **Clarify/Ask** | Pauses loop, REPL handles user interaction |
| **Reasoning Traces** | Auto-logs execute/observe steps per tool call |
| **Self-Critique** | Agent reviews own output before finalizing |

---

## Hybrid Routing

### Model Registry (`src/dhybrid/llm/registry.py`)

```python
class ModelRegistry:
    def resolve(self, preset: str) -> ModelConfig:
        # Resolves preset name to ModelConfig
        # Checks env var for API key
        # Handles fallback presets
```

### Provider Adapters (`src/dhybrid/llm/providers/`)

| Provider | Class | Features |
|----------|-------|----------|
| OpenAI | `OpenAIProvider` | Streaming, tools, token counting |
| Anthropic | `AnthropicProvider` | Streaming, tools, prompt caching |
| LiteLLM | `LiteLLMClient` | 100+ providers via LiteLLM |
| OpenCode Zen | `OpenCodeZenProvider` | Free tier, no API key needed |

### Escalation Chain

```yaml
model:
  chain: ["bynara-big", "openrouter-big", "anthropic-big"]  # preset names
```

Escalation triggers:
1. Quality score < threshold (default 70)
2. Build task with questions/repeated questions
3. API errors (rate limit, timeout) → retry with backoff → escalate

---

## Tools System

### Tool Registry (`src/dhybrid/tools/registry.py`)

```python
class ToolRegistry:
    def __init__(self, allowlist: list[str] | None = None):
        self._tools: dict[str, ToolSpec] = {}
        self.allowlist = set(allowlist or [])
        self.tool_count: dict[str, int] = {}
    
    def register(self, name: str, description: str, parameters: dict, fn: Callable):
        self._tools[name] = ToolSpec(name, description, parameters, fn)
    
    def execute(self, name: str, arguments: dict) -> str:
        # Validates allowlist, parameters, executes, tracks count
```

### Tool Definition

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema
    fn: Callable[..., Any]
```

### Tool Categories (70+ tools)

#### Core Tools
| Tool | Description |
|------|-------------|
| `terminal` | Execute shell commands (with safety gate) |
| `read_file` / `write_file` / `apply_patch` | File operations |
| `grep` / `find_files` | Search |
| `git_status` / `git_diff` / `git_commit` / `git_log` | Git operations |
| `run_tests` | pytest runner |
| `web_fetch` / `web_search` / `http_request` | Web operations |
| `read_image` | Vision (GPT-4V + OCR fallback) |

#### Code Analysis
| Tool | Description |
|------|-------------|
| `code_map` / `code_map_multi` | AST-based code map (tree-sitter) |
| `dep_graph` | Dependency graph visualization |
| `semantic_search` | Vector-based code search (sqlite-vec) |

#### Language Toolchains
| Language | Tools |
|----------|-------|
| **Go** | `go_test`, `go_vet`, `go_fmt`, `go_build`, `go_mod_tidy`, `golangci_lint`, `gosec` |
| **Rust** | `cargo_test`, `cargo_build`, `cargo_check`, `cargo_fmt`, `cargo_clippy`, `cargo_audit`, `cargo_update`, `cargo_outdated` |
| **TypeScript/Node** | `npm_test`, `npm_build`, `npm_install`, `npm_audit`, `tsc_check`, `eslint_check`, `jest_test`, `vitest_test`, `prettier_fmt` |
| **Java** | `mvn_test`, `mvn_build`, `mvn_compile`, `mvn_package`, `mvn_clean`, `gradle_test`, `gradle_build`, `gradle_check`, `spotbugs_check`, `checkstyle_check` |
| **C#/.NET** | `dotnet_test`, `dotnet_build`, `dotnet_restore`, `dotnet_clean`, `dotnet_fmt`, `dotnet_format`, `dotnet_tool_install`, `dotnet_outdated`, `dotnet_ef_migrations` |

#### Code Generation
| Tool | Input → Output |
|------|----------------|
| `codegen_openapi` | OpenAPI 3.0 → FastAPI + Pydantic |
| `codegen_graphql` | GraphQL Schema → Strawberry + SQLAlchemy |
| `codegen_protobuf` | Protobuf → gRPC Python + Pydantic |

#### CI/CD & Database
| Tool | Description |
|------|-------------|
| `ci_cd` | Generate GitHub Actions / GitLab CI |
| `db_migrate` | Alembic-compatible migration generator |

#### Memory & Skills
| Tool | Description |
|------|-------------|
| `episodic_remember` / `recall` / `recent` / `forget` | Cross-session episodic memory |
| `semantic_search` | Vector code search |
| `orchestrator` | Multi-agent planner/executor/reviewer |
| `mem_index` / `mem_search` / `mem_reset` | Project memory |

#### Observability
| Tool | Description |
|------|-------------|
| `prometheus_exporter` | Prometheus metrics + HTTP server |
| `opentelemetry` | Distributed tracing |

### Tool Execution Flow

```python
def execute(self, name: str, arguments: dict) -> str:
    # 1. Check allowlist
    if self.allowlist and name not in self.allowlist:
        return f"ERROR: tool '{name}' not allowed"
    
    # 2. Validate parameters (JSON Schema)
    cleaned = validate_args(self._tools[name].parameters, arguments)
    
    # 3. Execute
    self.tool_count[name] = self.tool_count.get(name, 0) + 1
    try:
        result = self._tools[name].fn(**cleaned)
        return str(result)
    except TypeError as e:
        return f"ERROR argumen {name}: {e}"
    except Exception as e:
        return f"ERROR {name}: {type(e).__name__}: {e}"
```

---

## Skills System

### Skill Format (`SKILL.md`)

```markdown
---
name: my-skill
description: Human-readable description for skill selection
version: 1.0.0
tags: [category, subcategory]
author: your-name
---

# Skill Name

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

### Skill Loader (`src/dhybrid/skills/loader.py`)

```python
@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

def list_skills(skills_dir: str | Path) -> list[Skill]:
    # Loads all SKILL.md from directory

def select_skills(
    prompt: str,
    skills: list[Skill],
    history: str = "",
    force: list[str] | None = None,
    min_score: int = 1,
    fallback: str | None = "general"
) -> list[str]:
    # Returns skill names sorted by relevance score
    # Scoring: keyword match (×2), history match (×1), fuzzy match (rapidfuzz)
    # Force skills always included
    # Fallback to "general" if no matches

def inject_skills(
    prompt: str,
    skills: list[Skill],
    max_inject: int = 3,
    max_chars: int = 800,
    history: str = "",
    force: list[str] | None = None,
    fallback: str | None = "general"
) -> str:
    # Prepends skill bodies to prompt
```

### Auto-Skill Learning

```python
def auto_skill_worthwhile(
    tools_used: list[str],
    tool_counts: dict[str, int] | None = None,
    final: str = "",
    files_created: int = 0,
    tests_passed: bool | None = None,
) -> bool:
    # Returns True if session produced real work:
    # - Files created > 0
    # - Mutating tools used (write_file, apply_patch, git_commit)
    # - Tests run
    # - Not trivial (greetings, "lanjutkan", etc.)
```

**Auto-learn triggers:**
- Files created > 0
- Mutating tools used
- Tests run
- Q&A repeated (≥75% similarity via rapidfuzz)

### Skill Marketplace (`src/dhybrid/skills/marketplace.py`)

```python
@dataclass
class SkillPackage:
    name: str
    description: str
    body: str
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)

def export_skill(skills_dir: str, skill_name: str, output_path: str) -> bool:
    # Exports skill to JSON package

def import_skill(skills_dir: str, package_path: str, overwrite: bool = False) -> bool:
    # Imports skill from JSON package

def list_published_skills(skills_dir: str) -> list[dict]:
    # Lists available skills

def search_skills(query: str, skills_dir: str) -> list[dict]:
    # Search by name/description
```

### Skill Composition (`src/dhybrid/skills/loader.py`)

```python
@dataclass
class SkillComposition:
    name: str
    description: str
    skill_names: list[str]
    composition_type: str = "sequence"  # "sequence" or "parallel"

def compose_skills(
    skills: list[Skill],
    name: str,
    description: str = "",
    composition_type: str = "sequence"
) -> Skill | None:
    # Combines multiple skills into workflow
    # Sequential (1→2→3) or Parallel (all at once)
```

---

## Memory & Context

### Session Store (`src/dhybrid/session/store.py`)

```python
class SessionStore:
    def __init__(self, db_path: Path):
        # SQLite with sessions, messages, summaries, checkpoints
    
    def new_session(self, cwd: str) -> str:
        # Creates new session, returns session_id
    
    def last_session_for_cwd(self, cwd: str) -> str | None:
        # Auto-resume last session in same directory
```

### Memory Store (`src/dhybrid/session/memory.py`)

```python
class MemoryStore:
    def __init__(self, db_path: Path):
        # SQLite + FTS5 for full-text search
    
    def remember(self, key: str, value: str) -> str:
        # KV store with FTS5 indexing
    
    def recall(self, key: str) -> str:
        # Exact key lookup
    
    def search(self, query: str, limit: int = 5) -> str:
        # FTS5 search across key + value
    
    def digest(self, context: str = "", limit: int = 8) -> str:
        # Relevant facts for current project/cwd
```

### Episodic Memory (`src/dhybrid/session/episodic_memory.py`)

```python
class EpisodicMemory:
    def __init__(self, db_path: Path):
        # SQLite + sentence-transformers embeddings
        # Vector similarity search
    
    def remember(self, task: str, outcome: str, tools: list[str], 
                 files: list[str], tags: list[str] = None) -> str:
        # Stores episode with embeddings
    
    def search(self, query: str, limit: int = 5, min_score: float = 0.7) -> list[dict]:
        # Semantic search across episodes
    
    def recent(self, limit: int = 10) -> list[dict]:
        # Most recent episodes
```

### Context Manager (`src/dhybrid/efficiency/context.py`)

```python
class ContextManager:
    def __init__(self, keep_recent: int = 8):
        self.keep_recent = keep_recent
        self.messages: list[ChatMessage] = []
        self.summary = ""
    
    def push(self, msg: ChatMessage):
        self.messages.append(msg)
    
    def render(self) -> list[ChatMessage]:
        # Returns: summary + recent messages (up to keep_recent)
    
    def compact(self, tokenizer, budget: TokenBudget) -> bool:
        # Summarizes old messages, keeps recent + summary
```

---

## Multi-Language Support

### Tree-sitter Integration

```python
# Supported languages via tree-sitter
LANGUAGES = {
    "python": "tree-sitter-python",
    "javascript": "tree-sitter-javascript",
    "typescript": "tree-sitter-typescript",
    "go": "tree-sitter-go",
    "rust": "tree-sitter-rust",
    "java": "tree-sitter-java",
    "c_sharp": "tree-sitter-c-sharp",
    "php": "tree-sitter-php",
}
```

### Code Map (`src/dhybrid/tools/code_map.py`)

```python
def generate_code_map(file_path: Path) -> dict:
    # Returns: functions, classes, imports, exports
    # Uses tree-sitter for accurate parsing
```

### Dependency Graph (`src/dhybrid/tools/dep_graph.py`)

```python
def generate_dep_graph(root: Path) -> dict:
    # Returns: nodes (files), edges (imports), cycles
```

### Semantic Search (`src/dhybrid/tools/semantic_search.py`)

```python
def index_workspace(workspace: Path):
    # Uses sqlite-vec + sentence-transformers
    # n-gram character embeddings for code

def semantic_search(query: str, workspace: Path, limit: int = 10):
    # Vector similarity search
```

---

## Observability

### Prometheus Metrics (`src/dhybrid/efficiency/prometheus_exporter.py`)

```python
# Standard metrics (Counter + Histogram)
tokens_prompt = Counter("tokens_prompt", "prompt tokens (tiktoken)")
tokens_completion = Counter("tokens_completion", "completion tokens")
tokens_cache = Counter("tokens_cache", "cached prompt tokens")
api_calls = Counter("api_calls", "total LLM API calls")
api_errors = Counter("api_errors", "LLM API errors")
turn_latency_ms = Counter("turn_latency_ms", "per-turn latency in ms")
cost_total_usd = Counter("cost_total_usd", "accumulated cost USD * 1e6")
tokens_total = Counter("tokens_total", "total tokens (prompt+completion)")

# Export format (Prometheus text exposition)
def export_metrics() -> str:
    # Returns: # HELP, # TYPE, metric lines
```

**HTTP Server:**
```python
server = start_metrics_server(port=9090)
# GET /metrics endpoint
```

### OpenTelemetry Tracing (`src/dhybrid/efficiency/tracing.py`)

```python
def init_tracing(service_name: str, otlp_endpoint: str = None) -> Tracer:
    # Initializes OpenTelemetry with OTLP exporter
    # Falls back to no-op if OTel not installed

class Tracer:
    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL):
        # Returns context manager for span
    
    def add_attribute(self, key: str, value: str):
        # Adds attribute to current span
```

### Structured Logging (`src/dhybrid/efficiency/metrics.py`)

```python
# Automatic logging via hooks
hooks.on_step = lambda step, model, usage, budget: log_usage(model, usage)
```

---

## Configuration

### Config File Locations

1. **Project:** `config/default.yaml` (committed)
2. **User:** `~/.dhybrid/config.yaml` (overrides project)
3. **Env vars:** Highest priority

### Key Sections

```yaml
workspace: ~/.dhybrid

model:
  provider: openai
  model: laguna-s-2.1-free
  base_url: https://opencode.ai/zen/v1
  api_key_env: OPENCODE_ZEN_API_KEY
  max_tokens: 4096
  temperature: 0.2
  chain: ["bynara-big", "openrouter-big", "anthropic-big"]

budget:
  soft: 60000
  hard: 120000

context:
  keep_recent: 8
  compact_ratio: 0.5

tool:
  max_output_chars: 8000
  allowlist: [terminal, read_file, write_file, ...]
  mcp_servers: []

skills:
  auto_learn: true
  max_inject: 3
  max_chars: 800
  fallback: "general"

clarify:
  enabled: true
  ai: true
  max_per_session: 3
```

### Presets (21 available)

| Category | Presets |
|----------|---------|
| OpenAI | `openai-fast` (gpt-4o-mini), `openai-big` (gpt-4o) |
| Anthropic | `anthropic-fast` (haiku), `anthropic-big` (sonnet) |
| OpenRouter | `openrouter-fast`, `openrouter-big` |
| Gemini | `gemini-fast`, `gemini-big` |
| Groq | `groq-fast` |
| DeepSeek | `deepseek-fast` |
| byNara | `bynara-fast/medium/big` |
| OpenCode Zen | `opencode-zen-fast/big/codex/nemotron/laguna/ling/mimo/north` (6 free) |

---

## CLI Interface

### Commands

| Command | Description |
|---------|-------------|
| `dhybrid repl` | Interactive REPL (default) |
| `dhybrid run "task"` | One-shot task execution |
| `dhybrid tokens [session_id]` | Token usage dashboard |
| `dhybrid resume <session_id>` | Resume session via summary |
| `dhybrid sessions` | List recent sessions |
| `dhybrid skills` | List available skills |
| `dhybrid doctor [--offline]` | Health check |
| `dhybrid self-update` | Update from GitHub |
| `dhybrid install` | Run installer (reinstall/update) |

### Global Options

| Option | Description |
|--------|-------------|
| `--config` | Config file path |
| `--cwd` | Working directory |
| `--model` | Override model preset |
| `--yes` | Auto-confirm dangerous commands |
| `--list-presets` | List available presets |

### REPL Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl-R` | History search |
| `Tab` | Auto-complete commands/skills |
| `Ctrl-C` | Cancel current task |
| `Ctrl-D` | Exit |

### Slash Commands (in REPL)

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/model <name>` | Switch model |
| `/key <provider> <value>` | Set API key |
| `/tokens` | Token dashboard |
| `/compact` | Compact context |
| `/sessions` | List sessions |
| `/skills` | List/enable skills |
| `/skill <name>` | Force skill |
| `/clear` | Reset conversation |
| `/quit` | Exit |

### Skill References

| Syntax | Description |
|--------|-------------|
| `@skill-name` | Force inject skill |
| `/skill name` | Force skill for session |
| `/skill off` | Disable forced skill |

---

## Testing

### Test Structure

```
tests/
├── unit/                    # Unit tests (498 tests)
│   ├── test_*.py           # Module-specific tests
│   └── conftest.py         # Shared fixtures
└── integration/            # Integration tests (15 tests)
    ├── test_e2e_workflows.py
    └── test_095_features.py
```

### Running Tests

```bash
# All tests
pytest -q

# Parallel (faster)
pytest -q -n auto

# With coverage
pytest -q --cov=src/dhybrid

# Specific test
pytest tests/unit/test_config.py -v

# Skip slow/flaky tests
pytest -x --ignore=tests/unit/test_episodic_memory.py --ignore=tests/unit/test_semantic_search.py
```

### Quality Gates

```bash
# Linting
ruff check .

# Security scan
bandit -q -r src/dhybrid -c .bandit.yml

# Dependency audit
pip-audit

# Pre-commit
pre-commit install
```

---

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

### Installer (`install.sh`)

```bash
# One-liner
curl -fsSL https://raw.githubusercontent.com/FerzDevZ/dhybrid-agent/main/install.sh | bash

# With uv (faster)
DHYBRID_USE_UV=1 curl -fsSL ... | bash

# Options:
DHYBRID_INSTALL_DIR=~/my-dhybrid
DHYBRID_BIN_DIR=~/bin
DHYBRID_BRANCH=main
DHYBRID_REPO_URL=https://github.com/...
DHYBRID_SKIP_ENV=1
DHYBRID_USE_UV=1
```

### CLI Update

```bash
dhybrid self-update
```

---

## Extending the Agent

### Adding a Custom Tool

```python
# src/dhybrid/tools/my_tool.py
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

```python
# In src/dhybrid/tools/__init__.py
from dhybrid.tools import my_tool

def build_tools(cfg, ...):
    # ...
    my_tool.register(reg, max_chars=max_chars)
```

### Custom Model Provider

```python
# src/dhybrid/llm/providers/custom.py
from dhybrid.llm.base import BaseProvider, ChatMessage

class CustomProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
    
    async def chat(self, messages, **kwargs):
        # Custom API call
        return response
```

Register in `src/dhybrid/llm/registry.py`.

### Custom Quality Scorer

```python
# src/dhybrid/agent/quality.py
def custom_quality_score(text: str, context: dict) -> int:
    """Score 0-100 based on custom criteria."""
    score = 100
    if "TODO" in text or "FIXME" in text:
        score -= 10
    if "def test_" in text:
        score += 5
    return max(0, min(100, score))
```

### Custom Hooks

```python
# src/dhybrid/agent/hooks.py
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

### Custom Skill Templates

```
~/.dhybrid/skills/templates/
├── api_endpoint.py      # FastAPI endpoint template
├── react_component.tsx  # React component template
├── k8s_deployment.yaml  # K8s deployment template
└── dockerfile           # Multi-stage Dockerfile
```

---

## Quick Reference: Key Files

| File | Purpose |
|------|---------|
| `src/dhybrid/cli.py` | CLI entry point |
| `src/dhybrid/config.py` | Configuration system |
| `src/dhybrid/agent/loop.py` | Agent ReAct loop |
| `src/dhybrid/agent/router.py` | Hybrid model routing |
| `src/dhybrid/tools/registry.py` | Tool registry |
| `src/dhybrid/tools/__init__.py` | Tool registration |
| `src/dhybrid/skills/loader.py` | Skill loading/injection |
| `src/dhybrid/skills/marketplace.py` | Skill import/export |
| `src/dhybrid/session/context.py` | SessionContext (central hub) |
| `src/dhybrid/session/store.py` | SQLite session storage |
| `src/dhybrid/session/memory.py` | KV + FTS5 memory |
| `src/dhybrid/session/episodic_memory.py` | Vector episodic memory |
| `src/dhybrid/efficiency/budget.py` | Token budget |
| `src/dhybrid/efficiency/context.py` | Context compaction |
| `src/dhybrid/efficiency/cache.py` | Prompt caching |
| `src/dhybrid/efficiency/metrics.py` | Observability metrics |
| `src/dhybrid/efficiency/prometheus_exporter.py` | Prometheus export |
| `src/dhybrid/efficiency/tracing.py` | OpenTelemetry tracing |
| `src/dhybrid/ui/repl.py` | REPL loop |
| `src/dhybrid/ui/commands.py` | Slash commands |
| `src/dhybrid/llm/registry.py` | Model registry |
| `src/dhybrid/llm/providers/` | Provider adapters |
| `install.sh` | One-line installer |

---

## License

MIT License — Data 100% local (`~/.dhybrid/`) — No telemetry.

---

*Generated from source code analysis of dhybrid-agent v0.9.6+*