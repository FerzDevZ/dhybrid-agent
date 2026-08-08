"""Escalation policy — cost/quality-based model escalation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from dhybrid.agent.hooks import Hooks
from dhybrid.llm.base import LLMClient


@dataclass
class EscalationConfig:
    """Configuration for escalation behavior."""
    escalation_chain: list[str] = field(default_factory=list)
    max_escalations: int = 2
    escalation_cooldown_steps: int = 3
    quality_threshold: int = 35
    client_factory: Callable[[str], LLMClient | None] | None = None
    # Konfirmasi user sebelum eskalasi. None = otomatis (mode lama).
    # false = tolak eskalasi.
    confirm_fn: Callable[[str], bool] | None = None


@dataclass
class EscalationResult:
    """Result of an escalation attempt."""
    escalated: bool
    new_client: LLMClient | None = None
    preset_name: str | None = None
    reason: str = ""
    escalation_count: int = 0


class EscalationPolicy:
    """Manages model escalation based on quality, errors, and task needs."""

    def __init__(
        self,
        config: EscalationConfig,
        hooks: Hooks,
    ):
        self.config = config
        self.hooks = hooks
        self._esc_idx = 0
        self._n_escalations = 0
        self._last_escalation_step = -999  # for cooldown

    def can_escalate(self, current_step: int) -> bool:
        """Check if escalation is allowed (respects max and cooldown)."""
        if self._n_escalations >= self.config.max_escalations:
            return False
        if self._esc_idx >= len(self.config.escalation_chain):
            return False
        if current_step - self._last_escalation_step < self.config.escalation_cooldown_steps:
            return False
        return self.config.client_factory is not None

    def escalate_for_quality(
        self,
        current_step: int,
        score: int,
        is_build: bool,
        asks_qa: bool,
        repeated_qa: bool,
    ) -> EscalationResult:
        """Escalate due to low quality score or asking questions during build."""
        if not self.can_escalate(current_step):
            return EscalationResult(escalated=False, reason="escalation not allowed")

        # Quality-based escalation
        if score < self.config.quality_threshold:
            return self._do_escalate(
                current_step,
                f"Skor kualitas rendah ({score}/100).",
            )

        # Build task asking questions -> escalate
        if is_build and (asks_qa or repeated_qa):
            return self._do_escalate(
                current_step,
                "Masih bertanya di tengah tugas membangun.",
            )

        return EscalationResult(escalated=False, reason="no quality escalation needed")

    def escalate_for_errors(
        self,
        current_step: int,
        error: Exception,
    ) -> EscalationResult:
        """Escalate due to API errors (transient or permanent)."""
        if not self.can_escalate(current_step):
            return EscalationResult(escalated=False, reason="escalation not allowed")

        return self._do_escalate(
            current_step,
            f"Gagal ke model sebelumnya ({type(error).__name__}).",
        )

    def _do_escalate(self, current_step: int, reason: str) -> EscalationResult:
        """Perform the escalation to next model in chain."""
        if self._esc_idx >= len(self.config.escalation_chain):
            return EscalationResult(escalated=False, reason="chain exhausted")

        if self.config.client_factory is None:
            return EscalationResult(escalated=False, reason="no client factory")

        # Gate izin user — AI tidak boleh eskalasi tanpa persetujuan.
        if self.config.confirm_fn is not None and not self.config.confirm_fn(reason):
            return EscalationResult(
                escalated=False, reason=f"user menolak eskalasi ({reason})"
            )

        self._esc_idx += 1
        self._n_escalations += 1
        self._last_escalation_step = current_step

        next_preset = self.config.escalation_chain[self._esc_idx - 1]
        client = self.config.client_factory(next_preset)

        if client is None:
            # Try next in chain
            return self._do_escalate(current_step, f"Preset {next_preset} unavailable")

        self.hooks.escalation(next_preset, reason)

        return EscalationResult(
            escalated=True,
            new_client=client,
            preset_name=next_preset,
            reason=reason,
            escalation_count=self._n_escalations,
        )

    def reset(self) -> None:
        """Reset escalation state for new run."""
        self._esc_idx = 0
        self._n_escalations = 0
        self._last_escalation_step = -999

    def get_status(self) -> dict:
        """Return current escalation status."""
        return {
            "escalation_count": self._n_escalations,
            "max_escalations": self.config.max_escalations,
            "current_preset_idx": self._esc_idx,
            "chain": self.config.escalation_chain,
        }