# Strategi Hemat Token

*You can't optimize what you don't measure* — semua teknik di bawah diukur via `/tokens` dan `dhybrid tokens`.

## 12 Teknik (urut dampak)

| # | Teknik | Mekanisme | Di mana |
|---|--------|-----------|---------|
| 1 | **Lazy policies** (Ponytail) | System prompt melarang kode tak diminta, memaksa edit minimal, grep helper dulu, "TIDAK ADA YANG PERLU DIUBAH" | `efficiency/lazy.py` |
| 2 | **Context compaction** | Pesan tua diringkas model kecil jadi summary; `keep_recent` pesan dipertahankan | `efficiency/context.py`, `compress.py` |
| 3 | **Prompt caching** | `cache_control: ephemeral` pada system (Anthropic); prefix caching otomatis (OpenAI/Gemini) | `llm/providers.py` |
| 4 | **Hybrid router** | Task mekanis → model murah; penalaran → model besar; klasifikasi di-cache | `agent/router.py` |
| 5 | **Tool output discipline** | `read_file` line-range, cap 8k chars, dedup, diff-based edit | `tools/*.py` |
| 6 | **Token budget** | soft → kompaksi; hard → stop | `efficiency/budget.py` |
| 7 | **System prompt compiled-once** | System + tool specs disusun sekali per sesi, bukan per turn | `session/context.py` |
| 8 | **JSON tool-call ringkas** | Tool-calling native + fallback blok JSON | `agent/parsing.py` |
| 9 | **Early-stop** | Hentikan loop saat jawaban final / sinyal "tidak ada perubahan" | `agent/loop.py` |
| 10 | **Semantic cache** | PromptCache SQLite (exact) + SemanticCache fuzzy (difflib) untuk klasifikasi/kompaksi berulang | `efficiency/cache.py` |
| 11 | **Resume via ringkasan** | Resume sesi memuat summary + 5 pesan terakhir, bukan transcript penuh | `cli.py`, `session/store.py` |
| 12 | **Metering** | Dashboard token/cache-hit/biaya per sesi | `ui/commands.py`, `cli.py` |

## Cara Mengukur Penghematan

```bash
# mode hemat ON
python -m tests.benchmarks.run_bench
# mode pembanding OFF (budget raksasa, tanpa router, tanpa kompaksi)
python -m tests.benchmarks.run_bench --off
```

Bandingkan total token & biaya dua laporan. Metrik kunci per sesi:

- **Cache-hit ratio** = `cached / prompt` — target ≥ 50% di Anthropic.
- **Routing split** = small:big — target ≥ 60% small.
- **Token/sesi** untuk task kecil — target ≤ 40k.
