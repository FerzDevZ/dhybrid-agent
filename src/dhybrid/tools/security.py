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
    """Deteksi perintah berbahaya — normalisasi spasi + kombinasi flag rm.

    Kebijakan:
    - `rm -rf`/`rm -fr` dst DITOLAK TANPA konfirmasi bila targetnya root `/`,
      rumah `/home/xxx`, atau path sistem (`/etc`, `/usr`, …) — ini menghancurkan
      keseluruhan, bukan sekadar konfirmasi.
    - rm -rf ke target spesifik di dalam workspace tetap lewat konfirmasi user.
    - traversal (`..`) di target juga selalu diblokir.
    
    Keamanan: meski parser pernah menghasilkan `rm -rf /home/firman/` dari input
    workspace, validator ini MENOLAK keluarga root `/home` berlapis — tidak ada
    jalan untuk menghapus rumah user via tool terminal.
    """
    c = re.sub(r"\s+", " ", command.strip())
    tokens = c.split()
    if not tokens:
        return False

    # semua pola berbahaya statis
    if any(p in c for p in DANGEROUS_PATTERNS):
        return True

    # deteksi `rm` dengan flag rekursif+force (rm -rf, rm -r -f, rm -fr, …)
    if "rm" in tokens:
        flags = "".join(t.lstrip("-") for t in tokens[1:] if t.startswith("-"))
        rm_rf = ("r" in flags and "f" in flags) or "rf" in flags or "fr" in flags
        if rm_rf:
            # kumpulkan target (token bukan flag)
            targets = [t for t in tokens[1:] if not t.startswith("-")]
            _FORBIDDEN_ROOTS = (
                "/", "/home", "/etc", "/usr", "/opt", "/srv", "/var",
                "/bin", "/sbin", "/lib", "/lib64", "/root",
                "/proc", "/sys", "/dev", "/boot",
            )

            def _is_bad_root(p: str) -> bool:
                if ".." in p:
                    return True
                try:
                    r = str(Path(p).expanduser().resolve())
                except (OSError, ValueError):
                    r = p
                # blokir root sistem + /home (dan /home/xxx apa saja) → tidak pernah hapus rumah
                return r in _FORBIDDEN_ROOTS or r == "/home" or r.startswith("/home/")

            # tidak ada target → berbahaya (rm -rf tanpa argumen = /)
            if not targets:
                return True
            # ada target tapi ada yang ke root/house/sistem/traversal → blokir total
            if any(_is_bad_root(t) for t in targets):
                return True
    return False
