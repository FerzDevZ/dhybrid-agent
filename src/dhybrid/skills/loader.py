"""Skills loader (gaya Hermes & OpenClaw) — SKILL.md + frontmatter.

Hemat token: hanya skill yang RELEVAN (skor keyword >= 1) yang di-inject,
max 3 skill, masing-masing dipotong max_chars.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


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


def build_skill_md(name: str, description: str, goal: str, tools_used: list[str], result: str) -> str:
    """Buat SKILL.md dari sesi yang sukses (auto-skill, gaya Hermes)."""
    tool_line = ", ".join(tools_used) if tools_used else "(tanpa tool)"
    return (
        f"---\nname: {name}\ndescription: {description}\n---\n\n"
        f"# {name}\n\n"
        f"**Tujuan:** {goal}\n\n"
        f"**Tools yang dipakai:** {tool_line}\n\n"
        f"**Langkah yang terbukti berhasil** (dari sesi nyata):\n\n"
        f"{result[:400]}\n"
    )


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
