from dhybrid.efficiency.budget import TokenBudget


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
