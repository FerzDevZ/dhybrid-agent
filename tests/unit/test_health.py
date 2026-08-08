from dhybrid.health import HealthMonitor


def test_healthy_on_no_data():
    h = HealthMonitor()
    assert h.is_healthy("foo")
    assert h.healthy_candidates(["a", "b"]) == ["a", "b"]


def test_two_failures_not_unhealthy_below_threshold():
    h = HealthMonitor(consecutive_failures=3, min_calls_for_health=10)
    for _ in range(2):
        h.record("p1", False)
    # min_calls_for_health > 2, dan consecutive < threshold → masih sehat
    assert h.is_healthy("p1")


def test_consecutive_failures_flag_unhealthy():
    h = HealthMonitor(consecutive_failures=2, min_calls_for_health=100)
    h.record("p", True)
    h.record("p", False)
    assert h.is_healthy("p")  # 1 gagal beruntun → aman
    h.record("p", False)
    assert not h.is_healthy("p")  # 2 gagal beruntun → buruk


def test_error_rate_flags_unhealthy():
    h = HealthMonitor(unhealthy_error_rate=0.5, min_calls_for_health=4, consecutive_failures=99)
    # 3 gagal, 1 berhasil: rate 0.75, calls >= 4 → buruk
    for ok in [True, False, False, False]:
        h.record("x", ok)
    assert not h.is_healthy("x")


def test_recovery_after_successful_run():
    h = HealthMonitor(consecutive_failures=1, recovery_calls=1, min_calls_for_health=100)
    h.record("p", False)
    assert not h.is_healthy("p")
    h.record("p", True)
    assert h.is_healthy("p")


def test_healthy_candidates_sorted_by_latency():
    h = HealthMonitor(min_calls_for_health=99, consecutive_failures=99)
    h.record("slow", True, latency_ms=9000)
    h.record("fast", True, latency_ms=50)
    h.record("medium", True, latency_ms=400)
    res = h.healthy_candidates(["slow", "fast", "medium"])
    assert res == ["fast", "medium", "slow"]


def test_healthy_candidates_drop_unhealthy():
    h = HealthMonitor(consecutive_failures=2, min_calls_for_health=99)
    h.record("bad", False)
    h.record("bad", False)
    h.record("good", True, latency_ms=10)
    res = h.healthy_candidates(["bad", "good"])
    assert res == ["good"]
    assert "bad" not in res
