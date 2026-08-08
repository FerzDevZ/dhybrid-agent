# Plan: Saran Peningkatan dhybrid-agent (Prioritas & Roadmap)

**Dibuat**: 2025-08-06  
**Berdasarkan**: Analisis full codebase (7 area arsitektur)  
**Tujuan**: Membuat agentic behavior lebih robust, adaptif, dan extensible

---

## Ringkasan Eksekutif

dhybrid-agent sudah memiliki fondasi solid: token efficiency end-to-end, auto-skill learning, hybrid routing, rich toolset. Kelemahan utama: **monolithic AgentLoop**, **heuristic-heavy** (keyword/regex), **no semantic understanding**, **static config**.

Rencana: **3 fase** (6-8 minggu total) fokus pada ROI tertinggi.

---

## Fase 1: Stabilitas & Kualitas (Minggu 1-3) — *Critical*

### 1.1 Refactor AgentLoop → State Machine
**File**: `src/dhybrid/agent/loop.py` (700+ baris → pecah jadi 4-5 file)

**Masalah**: Loop ReAct + nudge + quality + escalation + kompaksi bercampur, sulit test, race condition.

**Solusi**: State machine eksplisit:
```python
# loop/state_machine.py
class LoopState(Enum):
    THINKING = "thinking"
    EXECUTING = "executing"
    NUDGING = "nudging"
    ESCALATING = "escalating"
    COMPACTING = "compacting"
    COMPLETED = "completed"
    STUCK = "stuck"
```

**File baru**:
- `loop/state_machine.py` — state transitions, guards
- `loop/nudge_controller.py` — 5-level nudge logic
- `loop/escalation_policy.py` — cost/quality-based escalation
- `loop/step_executor.py` — single step execution (pure)

**Test**: Unit test per state transition, property-based test untuk loop termination.

---

### 1.2 Quality Scoring: ML-based (replace keyword heuristics)
**File**: `src/dhybrid/agent/quality.py`

**Masalah**: Keyword "apakah bisa", "saya akan" → false positive confused/refusal. Task sukses dapat 40/100.

**Solusi**: 
- **Opsi A (Ringan)**: fastText classifier (~5MB) dilatih dari log sesi nyata (prompt, tools, result, score manual)
- **Opsi B (Few-shot)**: LLM judge (model kecil) dengan 20-30 few-shot examples

**Implementasi**: `QualityScorer` interface → `HeuristicScorer` (fallback) + `MLScorer` (default jika model tersedia).

**Data**: Ekspor `tests/unit/test_quality.py` + sesi nyata → dataset training.

---

### 1.3 Dynamic Router Classification (ML + Cost/Quality)
**File**: `src/dhybrid/agent/router.py`

**Masalah**: Regex "mechanical vs reasoning" tidak akurat untuk prompt campuran. Chain escalation static.

**Solusi**:
- Feature: task_type (build/debug/explain), complexity_estimate (token), history (recent quality)
- Scorer: `RoutingScorer` → pilih model optimal: `argmax(quality / cost * latency_penalty)`
- Fallback: heuristik jika ML tidak tersedia

**Config baru** (`config/default.yaml`):
```yaml
router:
  use_ml: true
  ml_model_path: "~/.dhybrid/models/router.onnx"
  cost_weight: 0.3
  quality_weight: 0.5
  latency_weight: 0.2
```

---

## Fase 2: Extensibility & Intelligence (Minggu 4-6) — *High*

### 2.1 Skill Plugin System + Marketplace
**File**: `src/dhybrid/skills/loader.py`, `marketplace.py`

**Masalah**: Skill hardcoded di `build_tools()`, tidak extensible. Marketplace basic.

**Solusi**:
```python
# skills/plugin.py
@dataclass
class SkillPlugin:
    name: str
    version: str
    description: str
    tools: list[str]          # tools yang di-register
    prompt_prefix: str        # injection ke prompt
    dependencies: list[str]   # skill lain yang dibutuhkan
    parameters: dict          # {{var}} substitution

# Decorator
@skill(name="pytest-expert", version="1.0.0", tools=["run_tests"])
def pytest_expert_skill():
    return SkillPlugin(...)
```

**Auto-discovery**: Scan `skills/` + `~/.dhybrid/skills/` + project skills → register otomatis.

**Marketplace v2**:
- Semantic versioning + dependency resolution
- Rating + review + install count
- `dhybrid skill install pytest-expert@^1.0`

---

### 2.2 Semantic Memory (Embeddings) untuk Context Relevance
**File**: `src/dhybrid/session/memory.py`, baru `memory/semantic.py`

**Masalah**: `digest()` pakai FTS keyword match — tidak menangkap "cara setup redis" vs "redis config".

**Solusi**:
- Local embedding: `sentence-transformers/all-MiniLM-L6-v2` (22MB, CPU OK)
- Vector store: `faiss-cpu` (lightweight) atau `chromadb` (embedded)
- Index: `project_memory` + `skill_bodies` + `session_summaries`
- Retrieval: `semantic_search(query, k=5)` → inject ke prompt sebagai "relevant facts"

**Config**:
```yaml
memory:
  semantic:
    enabled: true
    model: "all-MiniLM-L6-v2"
    index_path: "~/.dhybrid/semantic_index.faiss"
    max_chunks: 10000
```

---

### 2.3 Session Branching & Merging (Git-like)
**File**: `src/dhybrid/session/store.py`, baru `session/branching.py`

**Masalah**: Tidak bisa eksperimen → commit ke main session. Kolaborasi terbatas.

**Solusi**:
```
Session tree:
  main (HEAD) ← merge feature/auth
    └─ feature/auth (branch)
    └─ experiment/refactor-db
```

**Commands**:
```bash
dhybrid session branch feature/auth
dhybrid session merge feature/auth
dhybrid session list --tree
```

**Storage**: SQLite `sessions` tambah kolom `parent_session_id`, `branch_name`. Messages copy-on-write.

---

## Fase 3: Polish & Advanced (Minggu 7-8) — *Medium/Low*

### 3.1 Predictive Budget & Cost Optimization
**File**: `src/dhybrid/efficiency/budget.py`, baru `efficiency/predictor.py`

**Fitur**:
- Estimasi token sebelum run (berdasarkan prompt + history + task_type)
- Warning proaktif: "Estimasi 180k token, budget 120k → perlu escalate model murah"
- Auto-switch model saat budget tipis: `agnes-2.5-flash` → `gpt-4o-mini` (lebih murah/token)

---

### 3.2 Config Wizard Refactor (UX)
**File**: `src/dhybrid/cli.py` → pisah ke `src/dhybrid/config/wizard.py`

**Step-based flow**:
1. Provider & API key (validasi koneksi real-time)
2. Model preset (tampilkan cost/quality/latency real)
3. Budget & context (slider + estimasi biaya per session)
4. Skills & auto-learn
5. Preview config.yaml → simpan

---

### 3.3 Tool Pipeline / Macro Tools
**File**: `src/dhybrid/tools/registry.py`, baru `tools/pipeline.py`

**Contoh**:
```python
# pipeline: grep → read → apply_patch
grep_pipeline = ToolPipeline(
    name="refactor-pattern",
    steps=[
        ToolStep("grep", {"pattern": "old_api"}),
        ToolStep("read_file", {"path": "{{grep.results[0].file}}"}),
        ToolStep("apply_patch", {"patch": "{{generate_patch}}"}),
    ]
)
```

---

### 3.4 Provider Health & Dynamic Fallback
**File**: `src/dhybrid/llm/providers.py`, baru `llm/health.py`

**Fitur**:
- Periodic health check (latency, error rate, rate limit)
- Auto-disable failing provider
- Prefer low-latency provider untuk mechanical task
- Keyring integration (1Password, Bitwarden, macOS Keychain)

---

## Decision Matrix

| Improvement | Impact | Effort | Risk | Dependencies | Recommended |
|-------------|--------|--------|------|--------------|-------------|
| AgentLoop State Machine | 🔴 Critical | High | Medium | - | ✅ Fase 1 |
| ML Quality Scorer | 🔴 Critical | Medium | Low | Training data | ✅ Fase 1 |
| Dynamic Router | 🔴 Critical | Medium | Low | ML Quality | ✅ Fase 1 |
| Skill Plugin System | 🟠 High | Medium | Low | - | ✅ Fase 2 |
| Semantic Memory | 🟠 High | Medium | Medium | Embedding model | ✅ Fase 2 |
| Session Branching | 🟠 High | High | Medium | Store schema | ✅ Fase 2 |
| Predictive Budget | 🟡 Medium | Low | Low | History data | ⏳ Fase 3 |
| Config Wizard | 🟡 Medium | Low | Low | - | ⏳ Fase 3 |
| Tool Pipeline | 🟢 Low | Medium | Low | Registry | ⏳ Fase 3 |
| Provider Health | 🟢 Low | Medium | Low | - | ⏳ Fase 3 |

---

## Asumsi & Keputusan Teknis

| Keputusan | Alasan |
|-----------|--------|
| **ML on-device (ONNX/fastText)** | Privacy, latency, offline-capable. Tidak kirim data ke cloud. |
| **FAISS over Chroma** | Lighter dependency, no server, adequate untuk <100k vectors. |
| **SQLite for session branching** | Existing store, ACID, copy-on-write sederhana. |
| **Keep heuristic fallback** | ML model bisa tidak tersedia (CPU only, no internet). |
| **Incremental migration** | Setiap fase shippable independently, tidak big-bang rewrite. |

---

## Verification Criteria per Fase

### Fase 1 (Minggu 3)
- [ ] AgentLoop state machine: 100% state transition test pass
- [ ] Quality ML: F1 > 0.85 pada dataset 500 sesi (confused/refusal/promise vs working)
- [ ] Router: Cost/quality ratio improve > 20% vs static chain
- [ ] All existing 572 tests pass + 50+ new tests

### Fase 2 (Minggu 6)
- [ ] Skill plugin: `dhybrid skill install x` works, auto-discovery OK
- [ ] Semantic memory: Recall@5 > 0.8 untuk "relevant facts" di 10 project sample
- [ ] Session branch/merge: Round-trip preserve messages + tools state

### Fase 3 (Minggu 8)
- [ ] Budget predictor: MAE < 15% pada 100 run sample
- [ ] Config wizard: < 3 menit setup baru, zero config error
- [ ] Provider health: Auto-failover < 5 detik saat provider down

---

## Next Steps

1. **User confirm priority** — apakah urutan fase ini sesuai kebutuhan?
2. **Resource check** — apakah ada constraint (CPU-only, no GPU, bandwidth)?
3. **Start Fase 1.1** — refactor AgentLoop state machine (foundation untuk yang lain)

---

*Plan ini living document — akan di-update berdasarkan feedback & hasil implementasi.*