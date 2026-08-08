"""HealthMonitor — pelacakan kesehatan provider LLM untuk failover proaktif.

Berbeda dengan escalation (reaktif, setelah error terjadi), monitor ini
mencatat SEMUA panggilan (sukses/gagal + latensi) per provider dalam window
geser, lalu menandai provider "unhealthy" via:
- error rate tinggi (>= unhealthy_error_rate, cukup data),
- kegagalan beruntun (>= consecutive_failures),
- latensi rata-rata melewati ambang (provider nge-lag).

AgentLoop memakai is_healthy() saat memilih model → menghindari provider
bermasalah SEBELUM dipanggil, tanpa biaya tambahan.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass
class ProviderHealth:
    key: str
    calls: int = 0
    ok: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    consecutive_failures: int = 0
    unhealthy_since: float | None = None
    last_success_at: float | None = None

    @property
    def error_rate(self) -> float:
        return self.errors / max(self.calls, 1)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.calls, 1)

    @property
    def is_tracked(self) -> bool:
        return self.calls > 0


class HealthMonitor:
    """Statistik geser per provider + klasifikasi sehat/tidak."""

    def __init__(
        self,
        unhealthy_error_rate: float = 0.5,
        consecutive_failures: int = 2,
        min_calls_for_health: int = 3,
        unhealthy_latency_ms: float = 120_000.0,
        recovery_calls: int = 1,
    ):
        self.unhealthy_error_rate = unhealthy_error_rate
        self.consecutive_failures = consecutive_failures
        self.min_calls_for_health = min_calls_for_health
        self.unhealthy_latency_ms = unhealthy_latency_ms
        self.recovery_calls = recovery_calls
        self._stats: dict[str, ProviderHealth] = {}

    def record(self, provider: str, success: bool, latency_ms: float = 0.0) -> None:
        """Catat satu hasil panggilan provider (sukses/gagal + latensi ms)."""
        st = self._stats.setdefault(provider, ProviderHealth(key=provider))
        st.calls += 1
        st.total_latency_ms += max(latency_ms, 0.0)
        if success:
            st.ok += 1
            st.consecutive_failures = 0
            st.unhealthy_since = None
            st.last_success_at = time()
        else:
            st.errors += 1
            st.consecutive_failures += 1

    def _is_healthy_stat(self, st: ProviderHealth) -> bool:
        if not st.is_tracked:
            return True  # belum ada data → anggap sehat
        if st.unhealthy_since is not None:
            # sudah pernah ditandai buruk; butuh recovery_calls sukses beruntun
            if st.consecutive_failures > 0:
                return False
            return st.ok >= st.calls - self.recovery_calls
        if st.calls >= self.min_calls_for_health:
            if st.error_rate >= self.unhealthy_error_rate:
                st.unhealthy_since = time()
                return False
            if st.avg_latency_ms >= self.unhealthy_latency_ms:
                st.unhealthy_since = time()
                return False
        if st.consecutive_failures >= self.consecutive_failures:
            st.unhealthy_since = time()
            return False
        return True

    def is_healthy(self, provider: str) -> bool:
        """False bila provider terbukti bermasalah (sebelum dihindari pemilihan)."""
        st = self._stats.get(provider)
        if st is None:
            return True
        return self._is_healthy_stat(st)

    def healthy_candidates(self, providers: list[str]) -> list[str]:
        """Urutkan kandidat: yang sehat dulu, lalu yang tercepat (avg latency)."""
        healthy = [p for p in providers if self.is_healthy(p)]
        return sorted(healthy, key=lambda p: self._stats[p].avg_latency_ms if p in self._stats else 0)

    def report(self) -> list[ProviderHealth]:
        """Snapshot statistik, diurutkan dari yang paling bermasalah."""
        return sorted(self._stats.values(), key=lambda s: (-s.error_rate, s.avg_latency_ms))

    def clear(self) -> None:
        self._stats.clear()
