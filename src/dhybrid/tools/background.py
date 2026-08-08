"""Async tools — jalankan perintah panjang di background tanpa blokir loop.

`run_bg(command, max_chars, timeout)` → mulai proses di thread & balas "job <id> running".
`poll_bg(job_id)` → status: running/done + output incremental (drain buffer).

Menghindari kebuntuan loop pada operasi lama (big build, install, test lama)
dan memungkinkan agent terus bekerja sambil menunggu. Aman: proses diberi
timeout & buffer output dibatasi oleh max_chars.
"""

from __future__ import annotations

import itertools
import subprocess
import threading
import time
from dataclasses import dataclass, field

from dhybrid.tools.security import is_dangerous

_id_counter = itertools.count(1)
_jobs: dict[int, BackgroundJob] = {}  # type: ignore[name-defined]
_jobs_lock = threading.Lock()

# Callback konfirmasi — sama seperti tool terminal.
confirm_fn: callable | None = None  # type: ignore[assignment]


@dataclass
class BackgroundJob:
    id: int
    command: str
    started_at: float
    status: str = "running"  # running | done | timeout | killed | error
    exit_code: int | None = None
    output: str = ""
    timeout: int = 300
    _proc: subprocess.Popen | None = None
    _done: threading.Event = field(default_factory=threading.Event)
    _max_chars: int = 8000

    def is_running(self) -> bool:
        return not self._done.is_set()


def _run_worker(job: BackgroundJob) -> None:
    assert job._proc is not None  # set sebelum thread start
    try:
        for raw in iter(job._proc.stdout.readline, ""):  # type: ignore[union-attr]
            if raw:
                job.output += raw
                # batasi buffer agar tidak bocor tak terbatas
                if len(job.output) > job._max_chars * 3:
                    job.output = job.output[-job._max_chars:]
                if job._done.is_set():
                    break
        job.exit_code = job._proc.wait()  # type: ignore[union-attr]
        # status sudah "timeout"/"killed" oleh watchdog → jangan timpa
        if job.status == "running":
            job.status = "done"
    except Exception as e:  # noqa: BLE001
        job.status = "error"
        job.output = f"[background error] {e}"
    finally:
        job._done.set()


def run_bg(command: str, timeout: int = 300, max_chars: int = 8000) -> str:
    """Mulai command di background, balas job id. Mirip gate keamanan terminal."""
    if not command or not command.strip():
        return "ERROR: command kosong."
    if is_dangerous(command):
        if confirm_fn is None:
            return "ERROR: perintah berbahaya & konfirmasi non-aktif — ditolak."
        if not confirm_fn(command):
            return "ERROR: perintah ditolak user."
    job = BackgroundJob(
        id=next(_id_counter),
        command=command,
        started_at=time.time(),
        timeout=timeout,
        _max_chars=max_chars,
    )
    try:
        # shell=True BY DESIGN: tool terminal memang jalankan shell, dijaga gate.
        # stderr di-merge ke stdout: pipe stderr terpisah yang tak pernah di-drain
        # bisa penuh (64KB) → proses terblokir menulis → worker deadlock.
        job._proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True  # nosec B602
        )
    except Exception as e:  # noqa: BLE001
        return f"[error] gagal start: {e}"
    with _jobs_lock:
        _jobs[job.id] = job
    threading.Thread(target=_run_worker, args=(job,), daemon=True).start()
    # watchdog timeout
    threading.Timer(job.timeout, _expire, (job,)).start()
    return f"[job #{job.id}] running — panggil poll_bg(job_id={job.id})"


def _expire(job: BackgroundJob) -> None:
    if not job._done.is_set():
        try:
            job._proc.kill()  # type: ignore[union-attr]
        except Exception:  # noqa: S110, BLE001
            pass
        job.status = "timeout"
        job.output = (job.output + f"\n[timeout setelah {job.timeout}s]").strip()
        job._done.set()


def poll_bg(job_id: int, max_chars: int = 8000) -> str:
    """Cek status job (running/done + output terkini)."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return f"ERROR: job {job_id} tidak dikenal."
    tail = job.output[-max_chars:] or "(belum ada output)"
    return f"[job {job_id}] status={job.status} exit={job.exit_code}\n{tail}"


def _cleanup(max_age_s: int = 3600) -> None:
    """Hapus job selesai yang sudah lama (utilitas internal; tidak wajib dipanggil)."""
    now = time.time()
    dead = [j for j in _jobs.values() if j._done.is_set() and now - j.started_at > max_age_s]
    for j in dead:
        _jobs.pop(j.id, None)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "run_bg",
        "Jalankan perintah shell PANJANG di background; balik job id (pilih jika command bisa >60s). Pakai poll_bg untuk cek hasil.",
        {"command": {"type": "string"}, "timeout": {"type": "integer"}},
        lambda command, timeout=300: run_bg(command, timeout=timeout, max_chars=max_chars),
    )
    reg.register(
        "poll_bg",
        "Poling status job background (dari run_bg) + output terkini.",
        {"job_id": {"type": "integer"}, "max_chars": {"type": "integer"}},
        lambda job_id, _max_chars=8000: poll_bg(int(job_id), max_chars=_max_chars),
    )