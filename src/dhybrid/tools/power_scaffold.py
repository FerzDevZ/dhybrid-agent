"""Tool power: scaffold — generate file dari template Jinja2.

Aman: resolusi path dicek tidak keluar dari direktori target (traversal
diblokir), undefined variable = error (StrictUndefined, bukan diam-diam kosong).
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_SUFFIX = ".j2"


def _scaffold(template_dir: str, target_dir: str, variables: dict) -> str:
    tdir = Path(template_dir)
    if not tdir.is_dir():
        return f"ERROR: template dir tidak ada: {template_dir}"
    tgt = Path(target_dir).resolve()
    env = Environment(
        loader=FileSystemLoader(str(tdir)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    created = 0
    tdir_real = tdir.resolve()
    for tmpl in sorted(tdir.rglob(f"*{_TEMPLATE_SUFFIX}")):
        # 1) template itu sendiri tidak boleh keluar dari template dir (symlink)
        if not tmpl.resolve().is_relative_to(tdir_real):
            return f"ERROR: template keluar dari template dir: {tmpl}"
        rel = tmpl.relative_to(tdir)
        dest = (tgt / rel.with_suffix("")).resolve()
        # 2) hasil render tidak boleh keluar dari target dir
        if not dest.is_relative_to(tgt):
            return f"ERROR: path traversal diblokir: {rel}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(rel.as_posix()).render(**variables))
        created += 1
    return f"OK: {created} file di-scaffold dari {template_dir} → {target_dir}"


def _default_need(reg, name, mods, description, parameters, fn) -> None:
    reg.register(name, description, parameters, fn)


def register(reg, _need=None, **kw) -> None:
    """Daftarkan scaffold; _need dipakai soft.py untuk soft-register."""
    (_need or _default_need)(
        reg,
        "scaffold",
        ["jinja2"],
        "Generate banyak file dari template Jinja2 (variabel di-render; aman anti path-traversal)",
        {
            "template_dir": {"type": "string"},
            "target_dir": {"type": "string"},
            "variables": {"type": "object"},
        },
        _scaffold,
    )
