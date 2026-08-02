"""Benchmark harness — jalankan 5 task coding, catat token & biaya, buat laporan.

Pemakaian:
    python -m tests.benchmarks.run_bench            # semua task, mode hemat ON
    python -m tests.benchmarks.run_bench --off      # mode OFF (tanpa kompaksi/cache/lazy)
    python -m tests.benchmarks.run_bench --task 1   # hanya task 1

Butuh API key (baca .env). Tanpa key, task dilewati dengan status SKIP.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tests.benchmarks.tasks import TASKS


def run_one(task: dict, index: int, off: bool) -> dict:
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore
    from dhybrid.ui.repl import run_agent

    tmp = Path(tempfile.mkdtemp(prefix="dhybrid-bench-"))
    for line in task["setup"].splitlines():
        subprocess.run(line, shell=True, cwd=tmp, check=False, capture_output=True, timeout=30)

    cfg = Config.load(ROOT / "config" / "default.yaml")
    if off:
        cfg.budget = {"soft": 10**9, "hard": 10**9}
        cfg.context = {"keep_recent": 10**6, "compact_ratio": 0.5}
        cfg.small_model = None  # matikan router
    store = SessionStore(tmp / "s.sqlite")
    ctx = SessionContext(cfg, store, cwd=str(tmp))
    start = datetime.now(UTC)
    final = run_agent(ctx, task["prompt"])
    elapsed = (datetime.now(UTC) - start).total_seconds()

    verify = subprocess.run(task["verify"], shell=True, cwd=tmp, capture_output=True, text=True, check=False)
    ok = verify.returncode == 0

    rows = store.usage(ctx.sid)
    tot_p = sum(r["prompt"] for r in rows)
    tot_c = sum(r["completion"] for r in rows)
    tot_cached = sum(r["cached"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    shutil.rmtree(tmp, ignore_errors=True)

    return {
        "task": f"{index}. {task['name']}",
        "ok": ok,
        "steps_tokens": tot_p + tot_c,
        "prompt": tot_p,
        "completion": tot_c,
        "cached": tot_cached,
        "cost": cost,
        "elapsed": round(elapsed, 1),
        "final": final[:120],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", action="store_true", help="mode hemat token OFF (pembanding)")
    ap.add_argument("--task", type=int, default=None, help="hanya task index tertentu (1-5)")
    args = ap.parse_args()

    results = []
    for i, task in enumerate(TASKS, start=1):
        if args.task and args.task != i:
            continue
        print(f"== task {i}: {task['name']} ({'OFF' if args.off else 'ON'}) ...", flush=True)
        results.append(run_one(task, i, args.off))

    mode = "OFF" if args.off else "ON"
    lines = [
        f"# Benchmark dhybrid-agent — mode {mode}",
        "",
        f"tanggal: {datetime.now(UTC).isoformat(timespec='minutes')}",
        "",
        "| task | status | tokens | prompt | completion | cached | biaya | waktu (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['task']} | {'✅' if r['ok'] else '❌'} | {r['steps_tokens']:,} | "
            f"{r['prompt']:,} | {r['completion']:,} | {r['cached']:,} | ${r['cost']:.4f} | {r['elapsed']} |"
        )
    tot = sum(r["steps_tokens"] for r in results)
    ok = sum(1 for r in results if r["ok"])
    lines += [
        "",
        f"**Total: {tot:,} token | {ok}/{len(results)} task sukses**",
        "",
        "Jalankan dua kali (ON & OFF) lalu bandingkan untuk mengukur % penghematan.",
    ]
    report = ROOT / f"docs/benchmark-{mode.lower()}-{datetime.now(UTC):%Y%m%d-%H%M}.md"
    report.parent.mkdir(exist_ok=True)
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nlaporan: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
