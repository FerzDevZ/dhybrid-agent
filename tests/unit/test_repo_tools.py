"""Tests tool repo: deteksi forge, list issue, buat issue, buat PR/MR."""

from __future__ import annotations

import subprocess

import pytest

from dhybrid.tools import repo


@pytest.mark.parametrize("url,expected", [
    ("git@github.com:owner/repo.git", ("github", "owner/repo")),
    ("https://github.com/owner/repo.git", ("github", "owner/repo")),
    ("git@gitlab.com:group/sub/repo.git", ("gitlab", "group/sub/repo")),
    ("https://gitlab.com/group/sub/repo.git", ("gitlab", "group/sub/repo")),
    ("https://gitlab.com/a/b.git", ("gitlab", "a/b")),
])
def test_parse_remote(url, expected):
    assert repo.parse_remote(url) == expected


def test_parse_remote_invalid():
    assert repo.parse_remote("") is None
    assert repo.parse_remote("git@repo.com:onlyrepo") is None


@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=tmp_path, check=True, capture_output=True
    )
    (tmp_path / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "checkout", "-q", "-b", "feature/fix"], cwd=tmp_path, check=True,
        capture_output=True,
    )
    return str(tmp_path)


def _resp(payload):
    from types import SimpleNamespace

    return SimpleNamespace(status_code=200, text="", json=lambda: payload)


def _fake_request(monkeypatch) -> list[dict]:
    """Stub httpx.request — catat panggilan; GET repo→default_branch, GET issues→list,
    POST issues→{number:7}, POST pulls→{number:42}."""
    calls: list[dict] = []

    def fake(method, url, *, json=None, params=None, **kw):
        calls.append({"method": method, "url": url, "json": json, "params": params})
        m = method.upper()
        if m == "POST":
            if url.endswith("/issues"):
                return _resp({"number": 7, "html_url": "https://x/7"})
            return _resp({"number": 42, "html_url": "https://x/42"})
        if url.endswith("/issues"):
            return _resp([
                {"number": 1, "title": "Perbaiki flow"},
                {"number": 2, "title": "Fix login"},
            ])
        return _resp({"default_branch": "main"})

    monkeypatch.setattr("httpx.request", fake)
    return calls


def test_repo_issues(monkeypatch, git_repo):
    _fake_request(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    out = repo.repo_issues(cwd=git_repo)
    assert "#1 Perbaiki flow" in out
    assert "#2 Fix login" in out


def test_repo_issue_create(monkeypatch, git_repo):
    calls = _fake_request(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    out = repo.repo_issue("Perbaiki flow", "body", cwd=git_repo)
    assert "issue #7" in out
    post = [c for c in calls if c["method"].upper() == "POST"][-1]
    assert post["url"] == "https://api.github.com/repos/owner/repo/issues"
    assert post["json"]["title"] == "Perbaiki flow"


def test_repo_pr_create(monkeypatch, git_repo):
    calls = _fake_request(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    out = repo.repo_pr("PR fix", "desc", cwd=git_repo)
    assert "PR #42" in out
    pr = [c for c in calls if "/pulls" in c["url"]][-1]
    assert pr["json"]["base"] == "main"
    assert pr["json"]["head"] == "feature/fix"


def test_repo_issue_no_token(monkeypatch, git_repo):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    out = repo.repo_issue("Judul", cwd=git_repo)
    assert out.startswith("ERROR") and "GITHUB_TOKEN" in out


def test_repo_issue_no_remote(tmp_path):
    out = repo.repo_issue("Judul", cwd=str(tmp_path))
    assert "ERROR" in out