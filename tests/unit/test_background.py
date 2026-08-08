import time

from dhybrid.tools import background


def test_run_bg_and_poll_roundtrip():
    background._jobs.clear()
    out = background.run_bg("echo hello-bg")
    assert "[job #" in out and "running" in out
    job_id = _extract_id(out)
    _wait_done(job_id)
    poll = background.poll_bg(job_id)
    assert "status=done" in poll
    assert "hello-bg" in poll


def test_run_bg_unknown_job():
    assert "ERROR" in background.poll_bg(99999999)


def test_run_bg_empty_command():
    assert "ERROR" in background.run_bg("")
    assert "ERROR" in background.run_bg("   ")


def test_poll_shows_accumulated_output_bounded():
    # output panjang dibatasi max_chars, tidak bocor tak terbatas
    background._jobs.clear()
    out = background.run_bg("printf 'a%.0s' {1..200000}")
    job_id = _extract_id(out)
    _wait_done(job_id)
    poll = background.poll_bg(job_id, max_chars=3000)
    assert len(poll) <= 3200
    assert "status=done" in poll


def test_dangerous_rejected_when_no_confirm():
    # tanpa confirm_fn default → berbahaya ditolak
    background.confirm_fn = None
    out = background.run_bg("rm -rf /")
    assert "ERROR" in out and "ditolak" in out


def _extract_id(out: str) -> int:
    return int(out.split("#")[1].split("]")[0])


def _wait_done(job_id: int):
    for _ in range(200):
        if "status=running" not in background.poll_bg(job_id):
            return
        time.sleep(0.02)