"""RunCheckpoint — snapshot loop di tengah jalan, untuk resume buntu/Ctrl-C.

Sederhana & JSON. Per langkah ke-N (LoopConfig.checkpoint_every), AgentLoop
menulis: step, budget.used+history, pesan konteks (role+content), prompt,
system_prompt, penghitung refleksi/repair. Pada resume, user membangun ulang
AgentLoop FRESH, muat checkpoint, dan `run()` melanjutkan dari langkah save
(seluruh konteks lama di-restore → tidak kehilangan pekerjaan).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunCheckpoint:
    run_id: str
    step: int = 0
    prompt: str = ""
    system_prompt: str = ""
    cwd: str = "."
    budget_used: int = 0
    budget_history: list[dict] = field(default_factory=list)
    reflect_iterations: int = 0
    repair_rounds: int = 0
    messages: list[dict] = field(default_factory=list)  # {role, content}

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> RunCheckpoint:
        return cls(**json.loads(text))


def _msg_to_dict(role: str, content: str | None) -> dict:
    return {"role": role, "content": content}


def save_run_checkpoint(path, ckpt: RunCheckpoint) -> str:
    """Tulis atomik (tmp + rename) supaya tidak corrupt bila crash di tengah."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(ckpt.to_json())
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return str(p)


def load_run_checkpoint(path) -> RunCheckpoint | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return RunCheckpoint.from_json(p.read_text(encoding="utf-8"))
    except (ValueError, KeyError):
        return None