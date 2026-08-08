"""Regression scenarios — kasus historis yang pernah rusak, dicek tiap CI.

Harness menjalankan AgentLoop dengan client scripted (offline) → guard
perubahan di masa depan tidak mengulang bug lama.
"""

from __future__ import annotations

from dhybrid.eval.harness import RegressionHarness, Scenario

SCENARIOS = [
    Scenario(
        name="build-with-evidence-not-nudged",
        prompt="buatkan file config",
        replies=["tool:write_file:x", "text:selesai, file dibuat"],
        expect_final_contains=["selesai"],
        expect_files_created=True,
    ),
    Scenario(
        name="build-without-evidence-stopped-early",
        prompt="kerjakan fitur login",
        replies=["text:oke saya kerjakan ya", "text:oke saya kerjakan ya"],
        max_nudges=1,
        expect_stopped_early=True,
    ),
    Scenario(
        name="qa-question-not-treated-as-stuck",
        prompt="kenapa error ini?",
        replies=["text:tepatnya errornya apa? bisa kasih detail?"],
        expect_final_contains=["detail"],
    ),
    Scenario(
        name="weak-answer-triggers-reflection",
        prompt="buatkan aplikasi",
        replies=["text:saya tidak bisa membantu di sini", "text:saya tidak bisa membantu di sini"],
        max_nudges=1,
        max_reflect=1,
    ),
    Scenario(
        name="done-with-evidence-no-reflection",
        prompt="buatkan file",
        replies=["tool:write_file:x", "text:selesai, file jadi"],
        max_reflect=0,
    ),
    # auto-verify menulis test .py yang GAGAL → model diberi [repair] untuk
    # memperbaiki (Verify→Repair loop). Setelah 1 repair masih gagal (scripted
    # tidak benar-benar memperbaiki), run berhenti normal dengan auto_verify False.
    Scenario(
        name="verify-fail-triggers-repair",
        prompt="buatkan modul",
        replies=[
            "tool:write_file:test_broken.py",
            "text:selesai, module temape",
            "tool:write_file:test_broken.py",
            "text:selesai, sudah diperbaiki",
        ],
        max_repair=1,
        expect_repair=True,
        expect_files_created=True,
    ),
]


def test_regression_scenarios():
    harness = RegressionHarness()
    results = harness.run_all(SCENARIOS)
    failures = [r for r in results if not r.passed]
    assert not failures, "\n".join(harness.report(results).splitlines()[:-1])