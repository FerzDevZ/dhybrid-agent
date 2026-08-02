"""Keamanan tool — cegah path traversal & akses lokasi sensitif.

Tool file (read/write/patch) TIDAK boleh menyentuh lokasi sistem atau
lokasi sensitif user; path traversal (../) keluar workspace diblokir.
"""

from __future__ import annotations

import re
from pathlib import Path

BLOCKED_ROOTS = (
    "/etc", "/boot", "/usr", "/root", "/var", "/opt", "/srv",
    "/bin", "/sbin", "/lib", "/lib64", "/dev", "/proc", "/sys", "/run",
)

SENSITIVE_PARTS = (
    "/.ssh/", "/.gnupg/", "/.aws/", "/.docker/", "/.git-credentials",
    "/.netrc", "/.bashrc", "/.zshrc", "/.profile", "/.config/",
    "authorized_keys", "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa",
)


def check_path_safe(path_str: str, base: Path | None = None) -> tuple[bool, str]:
    """Cek keamanan path untuk tool file. Return (ok, alasan).

    - traversal (..) keluar base → blokir
    - lokasi sistem (BLOCKED_ROOTS) → blokir
    - lokasi sensitif (.ssh, .bashrc, key, dsb) → blokir
    - menulis .env via tool → blokir (pakai /key atau /settings)
    """
    p = Path(path_str).expanduser()
    raw = str(path_str)
    allowed = (base or Path.cwd()).resolve()

    if ".." in raw:
        resolved = p.resolve()
        if not (str(resolved) == str(allowed) or str(resolved).startswith(str(allowed) + "/")):
            return False, f"path traversal keluar workspace diblokir: {path_str}"

    r = str(p.resolve())
    if any(r == b or r.startswith(b + "/") for b in BLOCKED_ROOTS):
        return False, f"lokasi sistem diblokir: {path_str}"
    low = r.lower()
    if any(sp in low for sp in SENSITIVE_PARTS):
        return False, f"lokasi sensitif diblokir: {path_str}"
    if p.name == ".env":
        return False, "menulis .env via tool diblokir — gunakan /key atau /settings"
    return True, ""


# ---- perintah berbahaya (terminal) ----

DANGEROUS_PATTERNS = [
    "rm -rf", "rm -fr", "rm -r -f", "rm -f -r", "rm --recursive --force", "rm --force --recursive",
    "git push --force", "git push -f", "git reset --hard origin",
    "mkfs", "dd if=", "shutdown", "reboot", "> /dev/sd", ":(){",
    "chmod -R 777 /", "chmod 777 /", "drop table", "DROP TABLE",
    "curl | sh", "wget | sh", "sudo rm", "sudo dd",
]


def is_dangerous(command: str) -> bool:
    """Deteksi perintah berbahaya — normalisasi spasi + kombinasi flag rm."""
    c = re.sub(r"\s+", " ", command.strip())
    if any(p in c for p in DANGEROUS_PATTERNS):
        return True
    # rm + flag recursive/force dalam urutan/format apa pun (rm -r -f, rm -fr, ...)
    tokens = c.split()
    if "rm" in tokens:
        flags = "".join(t for t in tokens if t.startswith("-"))
        if ("r" in flags and "f" in flags) or "rf" in flags or "fr" in flags:
            return True
    return False
