"""Skills loader (gaya Hermes & OpenClaw) — SKILL.md + frontmatter.

Hemat token: hanya skill yang RELEVAN (skor keyword >= 1) yang di-inject,
max 3 skill, masing-masing dipotong max_chars.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "ini", "itu",
    "saya", "anda", "kamu", "tolong", "bantu", "mohon", "please", "the", "and",
    "with", "agar", "supaya", "cara", "bagaimana", "bisa", "pakai",
    "menggunakan", "dll", "dst", "aja", "saja",
}


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _parse_skill_file(path: Path) -> Skill | None:
    text = path.read_text(errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    front, body = m.group(1), m.group(2).strip()
    name = re.search(r"^name:\s*(.+)$", front, re.MULTILINE)
    desc = re.search(r"^description:\s*(.+)$", front, re.MULTILINE)
    if not name:
        return None
    return Skill(
        name=name.group(1).strip().strip('"'),
        description=desc.group(1).strip().strip('"') if desc else "",
        body=body,
        path=path,
    )


def list_skills(skills_dir: str | Path) -> list[Skill]:
    d = Path(skills_dir)
    if not d.exists():
        return []
    out = []
    for sk in sorted(d.iterdir()):
        if sk.is_dir():
            md = sk / "SKILL.md"
            if md.exists():
                skill = _parse_skill_file(md)
                if skill:
                    out.append(skill)
        elif sk.name == "SKILL.md":
            skill = _parse_skill_file(sk)
            if skill:
                out.append(skill)
    return out


def _keywords(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", text.lower()))


def build_skill_md(name: str, description: str, goal: str, tools_used: list[str], result: str, steps: str | None = None) -> str:
    """Buat SKILL.md dari sesi yang sukses (auto-skill, gaya Hermes).

    Ringkas & hemat token: body dipotong ~400 karakter agar inject skill
    tidak membebani konteks.
    """
    tool_line = ", ".join(tools_used) if tools_used else "(tanpa tool)"
    parts = [
        f"---\nname: {name}\ndescription: {description}\n---\n\n",
        f"# {name}\n\n",
        f"**Tujuan:** {goal}\n\n",
        f"**Tools yang dipakai:** {tool_line}\n\n",
    ]
    if steps:
        parts.append(f"**Langkah yang terbukti berhasil** (dari sesi nyata):\n\n{steps[:300]}\n\n")
    else:
        parts.append(f"**Catatan dari sesi nyata:**\n\n{result[:400]}\n")
    return "".join(parts)


def slugify(goal: str) -> str:
    """Nama skill otomatis dari prompt: kata kunci pertama yang bermakna."""
    words = [w for w in re.findall(r"[a-z0-9]{2,}", goal.lower()) if w not in STOPWORDS]
    name = "-".join(words[:3])
    return (name or "task")[:40]


def auto_skill_worthwhile(tools_used: list[str], final: str) -> bool:
    """Task nyata = ada tool yang dipakai + jawaban bukan error.
    Sapaan seperti 'haloo?' (0 tool) TIDAK menghasilkan skill."""
    if not tools_used:
        return False
    return bool(final and not final.startswith("[error"))


def inject_skills(
    prompt: str,
    skills: list[Skill],
    max_inject: int = 3,
    max_chars: int = 800,
) -> str:
    """Tambahkan body skill yang relevan ke prompt (prefix)."""
    pk = _keywords(prompt)
    scored = []
    for sk in skills:
        if not sk.description:
            continue
        score = len(_keywords(sk.description) & pk)
        if score >= 1:
            scored.append((score, sk))
    scored.sort(key=lambda x: -x[0])
    parts = []
    for _, sk in scored[:max_inject]:
        body = sk.body[:max_chars]
        parts.append(f"[SKILL: {sk.name}]\n{body}")
    if not parts:
        return prompt
    return "\n\n".join(parts) + "\n\n---\n\n" + prompt
