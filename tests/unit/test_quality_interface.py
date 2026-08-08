"""Unit tests untuk QualityScorer interface (pluggable)."""

from __future__ import annotations

from dhybrid.agent.quality import (
    HeuristicScorer,
    QualityInput,
    build_quality_scorer,
    score_output,
)


def test_factory_defaults_to_heuristic():
    # tanpa model onnx → fallback heuristic
    scorer = build_quality_scorer(use_ml=False)
    assert isinstance(scorer, HeuristicScorer)


def test_build_quality_scorer_ml_falls_back():
    # use_ml=True tapi tidak ada model → masih heuristic (tidak crash)
    scorer = build_quality_scorer(use_ml=True, model_path=None)
    assert scorer.score(QualityInput(text="oke", tools_used=1)) >= 0


def test_heuristic_scorer_natural_phrasing_not_punished():
    scorer = HeuristicScorer()
    inp = QualityInput(
        text="Saya akan buatkan login register. Apakah kamu mau saya tambahkan validasi?",
        is_build=True,
        tools_used=5,
        files_created=2,
    )
    assert scorer.score(inp) >= 60


def test_heuristic_scorer_evidence_dominates():
    scorer = HeuristicScorer()
    # teks sama, beda bukti eksekusi → skor beda jauh
    a = scorer.score(QualityInput(text="Beres.", is_build=True, tools_used=0, files_created=0))
    b = scorer.score(QualityInput(text="Beres.", is_build=True, tools_used=6, files_created=2))
    assert b > a
    assert b >= 60


def test_empty_no_work_scores_zero():
    scorer = HeuristicScorer()
    assert scorer.score(QualityInput(text="", is_build=True, tools_used=0)) == 0


def test_back_compat_score_output():
    # API lama tetap jalan (delegasi ke HeuristicScorer)
    s = score_output("Selesai.", is_build=True, tools_used=4, files_created=1)
    assert 0 <= s <= 100
    assert s >= 60


def test_input_range_always_valid():
    scorer = HeuristicScorer()
    for i in range(-5, 20, 3):
        for f in range(-1, 6):
            s = scorer.score(QualityInput(text="kata" * i, tools_used=i, files_created=f))
            assert 0 <= s <= 100