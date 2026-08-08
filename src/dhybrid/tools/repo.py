"""Tool repo — interaksi GitHub/GitLab: list Issues, buat Issue, buat PR/MR.

Deteksi forge dari `git remote get-url origin`. Butuh token env:
- GitHub : GITHUB_TOKEN
- GitLab : GITLAB_TOKEN

`repo_issues` = read-only (boleh di Plan Mode).
`repo_issue` / `repo_pr` = MUTASI (diblokir Plan Mode via registry.readonly).
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse

TIMEOUT = 20.0


class RepoError(Exception):
    pass


def git_remote_url(cwd: str = ".") -> str:
    """URL remote origin (kosong bila bukan repo git)."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()


def parse_remote(url: str) -> tuple[str, str] | None:
    """(forge, path) — forge 'github'|'gitlab', path 'owner/repo'.

    Dukungan format: `git@host:o/r.git`, `https://host/o/r.git`, `ssh://git@host/o/r.git`.
    """
    if not url:
        return None
    if "git@github.com" in url:
        head = url.split(":", 1)[1]
        forge = "github"
    elif "git@gitlab.com" in url:
        head = url.split(":", 1)[1]
        forge = "gitlab"
    else:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        head = parsed.path
        forge = "gitlab" if ("gitlab" in host or "gitlab" in url) else "github"
    parts = [p for p in head.split("/") if p]
    if len(parts) < 2:
        return None
    repo = parts[-1]
    repo = repo.removesuffix(".git")
    owner = "/".join(parts[:-1]).strip("/")
    return forge, f"{owner}/{repo}"


def _creds(cwd: str = ".") -> tuple[str, str, str]:
    """(forge, api_base, token). Raise RepoError bila tidak ada remote/token."""
    parsed = parse_remote(git_remote_url(cwd))
    if parsed is None:
        raise RepoError("bukan repo git atau remote origin tidak ditemukan")
    forge, path = parsed
    if forge == "github":
        token = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
        if not token:
            raise RepoError("atur GITHUB_TOKEN untuk akses GitHub")
        return forge, f"https://api.github.com/repos/{path}", token
    token = os.environ.get("GITLAB_TOKEN", "") or os.environ.get("GITLAB_PRIVATE_TOKEN", "")
    if not token:
        raise RepoError("atur GITLAB_TOKEN untuk akses GitLab")
    enc = urllib.parse.quote(path, safe="")
    return forge, f"https://gitlab.com/api/v4/projects/{enc}", token


def _current_branch(cwd: str = ".") -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip() or ""
    except Exception:  # noqa: BLE001
        return ""


def _request(method: str, url: str, token: str, *, json=None, params=None) -> dict | list:
    import httpx

    resp = httpx.request(
        method, url,
        headers={"Authorization": f"Bearer {token}"},
        json=json,
        params=params,
        timeout=TIMEOUT,
    )
    if resp.status_code >= 300:
        raise RepoError(f"HTTP {resp.status_code}: {(resp.text or '')[:200]}")
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return {"_text": resp.text}


def _default_branch(forge: str, api: str, token: str) -> str:
    """Branch default repo (dari metadata repo)."""
    data = _request("get", api, token)
    if isinstance(data, dict):
        return data.get("default_branch", "main")
    return "main"


def repo_issues(limit: int = 10, cwd: str = ".", max_chars: int = 3000) -> str:
    """Daftar Issue terbuka dari remote origin (read-only)."""
    try:
        forge, api, token = _creds(cwd)
    except RepoError as e:
        return f"ERROR: {e}"
    try:
        state = "opened" if forge == "gitlab" else "open"
        data = _request("get", f"{api}/issues", token, params={"state": state, "per_page": limit, "page": 1})
        if not isinstance(data, list):
            return "ERROR: respons API tidak dikenali"
        lines = []
        for row in data:
            iid = row.get("iid" if forge == "gitlab" else "number")
            lines.append(f"#{iid} {str(row.get('title', ''))[:120]}")
        return "\n".join(lines).strip()[:max_chars] or "(tidak ada issue terbuka)"
    except RepoError as e:
        return f"ERROR: {e}"


def repo_issue(title: str, body: str = "", cwd: str = ".", max_chars: int = 2000) -> str:
    """Buat Issue di remote origin (membutuhkan token)."""
    if not title.strip():
        return "ERROR: judul issue kosong"
    try:
        forge, api, token = _creds(cwd)
    except RepoError as e:
        return f"ERROR: {e}"
    try:
        payload = {"title": title}
        if forge == "github":
            payload["body"] = body
        else:
            payload["description"] = body
        data = _request("post", f"{api}/issues", token, json=payload)
        if not isinstance(data, dict):
            return "ERROR: respons API tidak dikenali"
        iid = data.get("iid" if forge == "gitlab" else "number")
        url = data.get("html_url") or data.get("web_url") or ""
        return f"issue #{iid} dibuat — {url}".strip()
    except RepoError as e:
        return f"ERROR: {e}"


def repo_pr(title: str, body: str = "", cwd: str = ".", max_chars: int = 2000) -> str:
    """Buat Pull Request/Merge Request dari branch saat ini → branch default."""
    if not title.strip():
        return "ERROR: judul PR kosong"
    head = _current_branch(cwd)
    if not head:
        return "ERROR: tidak bisa membaca branch git"
    try:
        forge, api, token = _creds(cwd)
        base = _default_branch(forge, api, token)
    except RepoError as e:
        return f"ERROR: {e}"
    try:
        if forge == "github":
            data = _request(
                "post", f"{api}/pulls", token,
                json={"title": title, "body": body, "head": head, "base": base},
            )
            if not isinstance(data, dict):
                return "ERROR: respons API tidak dikenali"
            return f"PR #{data.get('number', '?')} — {data.get('html_url', '')}".strip()
        data = _request(
            "post", f"{api}/merge_requests", token,
            json={"title": title, "description": body, "source_branch": head, "target_branch": base},
        )
        if not isinstance(data, dict):
            return "ERROR: respons API tidak dikenali"
        return f"MR !{data.get('iid', '?')} — {data.get('web_url', '')}".strip()
    except RepoError as e:
        return f"ERROR: {e}"


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "repo_issues",
        "Daftar Issue terbuka dari remote origin (GitHub/GitLab). Read-only.",
        {"limit": {"type": "integer"}, "cwd": {"type": "string"}},
        lambda limit=10, cwd=".": repo_issues(limit, cwd=cwd, max_chars=max_chars),
    )
    reg.register(
        "repo_issue",
        "Buat Issue di remote origin (GitHub/GitLab). Butuh GITHUB_TOKEN/GITLAB_TOKEN.",
        {"title": {"type": "string"}, "body": {"type": "string"}, "cwd": {"type": "string"}},
        lambda title, body="", cwd=".": repo_issue(title, body, cwd=cwd, max_chars=max_chars),
    )
    reg.register(
        "repo_pr",
        "Buat Pull Request/Merge Request dari branch saat ini ke branch default.",
        {"title": {"type": "string"}, "body": {"type": "string"}, "cwd": {"type": "string"}},
        lambda title, body="", cwd=".": repo_pr(title, body, cwd=cwd, max_chars=max_chars),
    )
