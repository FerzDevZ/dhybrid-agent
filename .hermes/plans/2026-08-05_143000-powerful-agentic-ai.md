# Powerful Agentic AI Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Transform dhybrid-agent into a more powerful, versatile agentic AI by adding advanced capabilities: multi-language support, enhanced tooling, better memory/reasoning, and production-ready features.

**Architecture:** Extend the existing hybrid routing (small/big models), skill system, and subagent delegation with new capabilities while maintaining token efficiency. Add multi-language support (Go, Rust, TypeScript), advanced code intelligence (AST-based), persistent memory across sessions, and production features (monitoring, observability, CI/CD integration).

**Tech Stack:** Python 3.12+, tree-sitter (multi-lang), LiteLLM (100+ providers), SQLite/Redis for memory, Prometheus/Grafana for observability, pytest for testing, Ruff for linting.

---

## Phase 1: Core Infrastructure & Multi-Language Support

### Task 1: Add Tree-sitter grammars for Go, Rust, TypeScript, Java, C#

**Objective:** Enable AST-based code intelligence for 5 additional languages beyond Python/PHP/JS.

**Files:**
- Create: `src/dhybrid/tools/code_map_multi.py`
- Modify: `src/dhybrid/tools/__init__.py:43` (add to tool registration)
- Modify: `pyproject.toml:23-26` (add tree-sitter dependencies)
- Test: `tests/unit/test_code_map_multi.py`

**Step 1: Write failing test**
```python
def test_code_map_go_extracts_functions():
    from dhybrid.tools.code_map_multi import extract_symbols
    go_code = "package main\nfunc Hello() string { return \"world\" }"
    symbols = extract_symbols("test.go", go_code, "go")
    assert any(s["name"] == "Hello" and s["kind"] == "function" for s in symbols)
```

**Step 2: Run test to verify failure**
```bash
pytest tests/unit/test_code_map_multi.py::test_code_map_go_extracts_functions -v
# Expected: FAIL — module not found
```

**Step 3: Write minimal implementation**
```python
# src/dhybrid/tools/code_map_multi.py
from __future__ import annotations
import tree_sitter
from tree_sitter_languages import get_language, get_parser

LANGUAGES = {
    "go": "go",
    "rust": "rust",
    "typescript": "typescript",
    "java": "java",
    "c_sharp": "c_sharp",
}

def extract_symbols(path: str, code: str, lang: str) -> list[dict]:
    if lang not in LANGUAGES:
        return []
    parser = get_parser(LANGUAGES[lang])
    tree = parser.parse(code.encode())
    # ... AST traversal logic per language
    return symbols
```

**Step 4: Run test to verify pass**
```bash
pytest tests/unit/test_code_map_multi.py::test_code_map_go_extracts_functions -v
# Expected: PASS
```

**Step 5: Commit**
```bash
git add pyproject.toml src/dhybrid/tools/code_map_multi.py src/dhybrid/tools/__init__.py tests/unit/test_code_map_multi.py
git commit -m "feat: add multi-language AST support (Go, Rust, TS, Java, C#)"
```

---

### Task 2: Add dependency graph visualization tool

**Objective:** Let agents understand cross-file dependencies for any supported language.

**Files:**
- Create: `src/dhybrid/tools/dep_graph.py`
- Modify: `src/dhybrid/tools/__init__.py:43` (register)
- Test: `tests/unit/test_dep_graph.py`

**Step 1: Write failing test**
```python
def test_dep_graph_python_imports():
    from dhybrid.tools.dep_graph import build_dependency_graph
    files = {"a.py": "import b", "b.py": "import c", "c.py": ""}
    graph = build_dependency_graph(files, "python")
    assert graph["a.py"] == ["b.py"]
```

**Step 2-5:** Similar TDD cycle, implement using tree-sitter imports/requires/uses extraction.

---

### Task 3: Add semantic code search (vector embeddings)

**Objective:** Enable "find code similar to X" across the codebase using embeddings.

**Files:**
- Create: `src/dhybrid/tools/semantic_search.py`
- Modify: `pyproject.toml` (add `sentence-transformers`, `faiss-cpu`)
- Test: `tests/unit/test_semantic_search.py`

**Step 1: Write failing test**
```python
def test_semantic_search_finds_similar():
    from dhybrid.tools.semantic_search import SemanticSearch
    ss = SemanticSearch()
    ss.index({"auth.py": "def login(user): ...", "user.py": "class User: ..."})
    results = ss.search("authentication function")
    assert "auth.py" in [r[0] for r in results]
```

---

## Phase 2: Enhanced Memory & Reasoning

### Task 4: Persistent episodic memory with SQLite + vector store

**Objective:** Remember past tasks, decisions, and patterns across sessions permanently.

**Files:**
- Create: `src/dhybrid/session/episodic_memory.py`
- Modify: `src/dhybrid/session/__init__.py` (export)
- Modify: `src/dhybrid/tools/memory.py` (register enhanced tools)
- Test: `tests/unit/test_episodic_memory.py`

**Step 1: Write failing test**
```python
def test_episodic_memory_stores_and_recalls():
    from dhybrid.session.episodic_memory import EpisodicMemory
    mem = EpisodicMemory(":memory:")
    mem.remember("task_123", "Implemented JWT auth with RS256", tags=["auth", "jwt"])
    results = mem.recall("JWT authentication")
    assert len(results) == 1
    assert "RS256" in results[0]["content"]
```

**Step 2-5:** Implement with SQLite FTS5 + sentence-transformers embeddings for semantic recall.

---

### Task 5: Add reasoning traces / chain-of-thought logging

**Objective:** Capture and display the agent's reasoning process for debugging and learning.

**Files:**
- Create: `src/dhybrid/agent/reasoning.py`
- Modify: `src/dhybrid/agent/loop.py:419` (integrate into run loop)
- Test: `tests/unit/test_reasoning.py`

**Step 1: Write failing test**
```python
def test_reasoning_trace_captures_steps():
    from dhybrid.agent.reasoning import ReasoningTrace
    trace = ReasoningTrace()
    trace.add_step("analyze", "User wants login", ["read_file:auth.py"])
    trace.add_step("plan", "Will implement JWT", ["write_file:auth.py"])
    steps = trace.get_steps()
    assert len(steps) == 2
    assert steps[0]["phase"] == "analyze"
```

---

### Task 6: Implement self-reflection / critique loop

**Objective:** Agent reviews its own output before finalizing, catches bugs early.

**Files:**
- Modify: `src/dhybrid/agent/loop.py:147` (enable self_critique)
- Modify: `src/dhybrid/agent/quality.py` (add critique prompt)
- Test: `tests/integration/test_self_critique.py`

**Step 1: Write failing test**
```python
def test_self_critique_catches_missing_test():
    from dhybrid.agent.loop import AgentLoop
    # Setup loop with self_critique=True
    # Give task that produces code without tests
    # Verify critique triggers and requests test addition
```

---

## Phase 3: Advanced Agent Capabilities

### Task 7: Multi-agent orchestration (planner + executor + reviewer)

**Objective:** Decompose complex tasks into sub-tasks handled by specialized subagents.

**Files:**
- Create: `src/dhybrid/agent/orchestrator.py`
- Create: `src/dhybrid/tools/orchestrator.py` (tool registration)
- Modify: `src/dhybrid/tools/__init__.py:49` (register)
- Test: `tests/integration/test_orchestrator.py`

**Step 1: Write failing test**
```python
def test_orchestrator_decomposes_feature():
    from dhybrid.agent.orchestrator import Orchestrator
    orch = Orchestrator(client_factory, tools)
    plan = orch.plan("Build REST API with auth, users, posts")
    assert len(plan.tasks) >= 3
    assert any(t["role"] == "planner" for t in plan.tasks)
    assert any(t["role"] == "executor" for t in plan.tasks)
    assert any(t["role"] == "reviewer" for t in plan.tasks)
```

---

### Task 8: Add code generation from specs (OpenAPI, GraphQL, Protobuf)

**Objective:** Generate boilerplate from specification files.

**Files:**
- Create: `src/dhybrid/tools/codegen.py`
- Modify: `pyproject.toml` (add `openapi-spec-validator`, `graphql-core`, `protobuf`)
- Test: `tests/unit/test_codegen.py`

**Step 1: Write failing test**
```python
def test_codegen_openapi_creates_fastapi_routes():
    from dhybrid.tools.codegen import generate_from_openapi
    spec = {"paths": {"/users": {"get": {"responses": {"200": {}}}}}}
    code = generate_from_openapi(spec, "fastapi")
    assert "@app.get('/users')" in code
```

---

### Task 9: Database migration tool (auto-generate Alembic migrations)

**Objective:** Agent can create and run database migrations safely.

**Files:**
- Create: `src/dhybrid/tools/db_migrate.py`
- Modify: `pyproject.toml` (add `alembic`, `sqlalchemy`)
- Test: `tests/unit/test_db_migrate.py`

**Step 1: Write failing test**
```python
def test_db_migrate_creates_migration():
    from dhybrid.tools.db_migrate import create_migration
    # Mock SQLAlchemy models
    migration = create_migration("add_users_table", models=[User])
    assert "CREATE TABLE users" in migration.up_sql
```

---

## Phase 4: Production Features & Observability

### Task 10: Prometheus metrics + Grafana dashboard

**Objective:** Monitor agent performance, token usage, quality scores in production.

**Files:**
- Modify: `src/dhybrid/efficiency/prometheus_exporter.py` (expand metrics)
- Create: `monitoring/grafana-dashboard.json`
- Create: `docker-compose.monitoring.yml`
- Test: `tests/unit/test_prometheus_metrics.py`

**Step 1: Write failing test**
```python
def test_prometheus_exporter_records_token_usage():
    from dhybrid.efficiency.prometheus_exporter import PrometheusExporter
    exp = PrometheusExporter()
    exp.record_usage("gpt-4o", 1000, 500, 0.02)
    # Verify metrics exposed on /metrics endpoint
```

---

### Task 11: Structured logging + distributed tracing (OpenTelemetry)

**Objective:** Debug production issues with full request traces.

**Files:**
- Create: `src/dhybrid/utils/tracing.py`
- Modify: `src/dhybrid/agent/loop.py` (add spans)
- Modify: `pyproject.toml` (add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`)
- Test: `tests/unit/test_tracing.py`

---

### Task 12: CI/CD integration (GitHub Actions, GitLab CI)

**Objective:** Agent can create and fix CI pipelines automatically.

**Files:**
- Create: `src/dhybrid/tools/ci_cd.py`
- Modify: `src/dhybrid/tools/__init__.py` (register)
- Test: `tests/unit/test_ci_cd.py`

**Step 1: Write failing test**
```python
def test_ci_cd_creates_github_actions_workflow():
    from dhybrid.tools.ci_cd import generate_github_actions
    workflow = generate_github_actions("python", test_cmd="pytest", lint_cmd="ruff")
    assert "on: [push, pull_request]" in workflow
    assert "pytest" in workflow
```

---

## Phase 5: Language-Specific Power Tools

### Task 13: Go toolchain integration (go mod, go test, go vet, gosec)

**Files:**
- Create: `src/dhybrid/tools/go_toolchain.py`
- Test: `tests/unit/test_go_toolchain.py`

### Task 14: Rust toolchain integration (cargo test, clippy, rustfmt, cargo-audit)

**Files:**
- Create: `src/dhybrid/tools/rust_toolchain.py`
- Test: `tests/unit/test_rust_toolchain.py`

### Task 15: TypeScript/Node toolchain (npm, tsc, eslint, jest, vitest)

**Files:**
- Create: `src/dhybrid/tools/ts_toolchain.py`
- Test: `tests/unit/test_ts_toolchain.py`

### Task 16: Java/Maven/Gradle toolchain

**Files:**
- Create: `src/dhybrid/tools/java_toolchain.py`
- Test: `tests/unit/test_java_toolchain.py`

### Task 17: C#/dotnet toolchain

**Files:**
- Create: `src/dhybrid/tools/dotnet_toolchain.py`
- Test: `tests/unit/test_dotnet_toolchain.py`

---

## Phase 6: Advanced Skills & Learning

### Task 18: Skill marketplace / sharing (import/export skills)

**Files:**
- Create: `src/dhybrid/skills/marketplace.py`
- Modify: `src/dhybrid/skills/loader.py` (add import/export)
- Test: `tests/unit/test_skill_marketplace.py`

### Task 19: Auto-skill improvement from user feedback

**Files:**
- Modify: `src/dhybrid/ui/repl.py` (add feedback collection)
- Modify: `src/dhybrid/skills/loader.py:266` (enhance auto_skill_worthwhile)
- Test: `tests/integration/test_skill_feedback.py`

### Task 20: Skill composition (combine skills for complex workflows)

**Files:**
- Create: `src/dhybrid/skills/composer.py`
- Test: `tests/unit/test_skill_composer.py`

---

## Phase 7: Configuration & Polish

### Task 21: Enhanced config.yaml with all new features

**Files:**
- Modify: `config/default.yaml` (add all new presets, tool settings, feature flags)

### Task 22: Comprehensive integration tests

**Files:**
- Create: `tests/integration/test_full_agentic_workflow.py`
- Create: `tests/integration/test_multi_language_project.py`

### Task 23: Documentation & examples

**Files:**
- Create: `docs/advanced-usage.md`
- Create: `docs/multi-language.md`
- Create: `docs/production-deployment.md`
- Create: `examples/` (sample projects per language)

---

## Risks, Tradeoffs & Open Questions

| Risk | Mitigation |
|------|------------|
| Token cost explosion with multi-agent | Strict budget limits per subagent; cheap models for planning |
| Tree-sitter grammar maintenance | Pin versions; test on CI per language |
| Vector embeddings latency | Cache embeddings; use local models (sentence-transformers) |
| Skill explosion (too many) | Auto-prune unused skills; max_inject=3 limit |
| Breaking existing workflows | Feature flags; backward-compatible defaults |

**Open Questions:**
1. Should we add a hosted vector DB option (Pinecone, Weaviate) or keep local-only?
2. Default embedding model: all-MiniLM-L6-v2 (fast, 384-dim) or larger?
3. Enable multi-agent orchestration by default or behind flag?
4. How to handle API keys for 100+ providers securely in team settings?

---

## Verification Commands

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run specific phase tests
pytest tests/unit/test_code_map_multi.py -v
pytest tests/unit/test_dep_graph.py -v
pytest tests/unit/test_semantic_search.py -v
pytest tests/unit/test_episodic_memory.py -v
pytest tests/integration/test_orchestrator.py -v

# Lint & type check
ruff check src/
mypy src/

# Build verification
pip install -e ".[dev,power,vision,redis]"
dhybrid doctor
```

---

## Execution Handoff

**Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed with Phase 1 (Tasks 1-3)?**