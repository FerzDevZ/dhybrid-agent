from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.predictor import TokenPredictor


def test_budget_lifecycle():
    b = TokenBudget(soft=100, hard=200)
    assert not b.should_compact
    b.add(60, 40, tag="turn1")
    assert b.should_compact and not b.exhausted
    b.add(60, 40, tag="turn2")
    assert b.exhausted


def test_cache_hit_ratio():
    b = TokenBudget(soft=1000, hard=2000)
    b.add(900, 100, cached=800)
    assert abs(b.cache_hit_ratio - 800 / 900) < 1e-9


def test_reset():
    b = TokenBudget(soft=10, hard=20)
    b.add(5, 5)
    b.reset()
    assert b.used == 0 and b.history == []


def test_predictor_ok_for_low_projection():
    """Proyeksi kecil (run pendek, avg kecil) → level OK, sisa positif luas."""
    p = TokenPredictor(hard_budget=100_000, warning_fraction=0.75, critical_fraction=0.9)
    res = p.predict(
        prompt="apa itu x", system_prompt="sys", used=3000, steps_done=1, history=[],
    )
    assert res.level.value == "ok"
    assert res.projected_total <= 100_000
    assert res.remaining > 0


def test_predictor_warning_and_critical():
    """avg/langkah nyata besar + banyak langkah tersisa → WARNING lalu CRITICAL."""
    p = TokenPredictor(hard_budget=10_000, warning_fraction=0.5, critical_fraction=0.9)
    fat_history = [{"prompt": 9000, "completion": 1000}] * 3  # avg 10k/langkah
    pred = p.predict(
        prompt="buatkan sistem auth penuh", system_prompt="sys",
        used=20_000, steps_done=5, history=fat_history,
    )
    assert pred.level.value in {"warning", "critical"}
    assert pred.projected_total > p.hard_budget


def test_predictor_steps_bounded():
    """estimate_steps tetap dalam [1,20] untuk prompt ekstrem."""
    assert 1 <= TokenPredictor.estimate_steps("") <= 20
    assert 1 <= TokenPredictor.estimate_steps("build full auth+db+api+ml platform") <= 20


def test_predictor_uses_real_history_avg():
    """avg dari history nyata dipakai bila tersedia (bukan anchor ~150)."""
    p = TokenPredictor(hard_budget=100_000)
    history = [{"prompt": 4000, "completion": 1000}] * 3  # avg 5000
    pred = p.predict("x", "sys", used=5000, steps_done=1, history=history, est_steps=3)
    # projected = 5000 (used) + 5000*2 (avg × sisa langkah) = 15000
    assert pred.projected_total == 15000
    assert pred.remaining == 100_000 - 15000
