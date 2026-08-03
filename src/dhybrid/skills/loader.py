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

# Sinonim/kata pemicu: prompt yang tidak menyebut kata persis di deskripsi skill
# tetap bisa mencocokkan. Contoh: "program saya crash" → konsep debugging.
ALIAS_EXPANSIONS = {
    # debugging & analisis error
    "debug": {"error", "traceback", "bug", "crash", "gagal", "exception"},
    "debugging": {"debug", "error", "traceback", "bug"},
    "error": {"debug", "traceback", "crash", "exception", "gagal", "bug"},
    "crash": {"debug", "error", "exception", "gagal", "mati", "rusak"},
    "traceback": {"debug", "error", "stack"},
    "exception": {"debug", "error", "crash"},
    "bug": {"debug", "error", "perbaiki", "fix", "rusak"},
    "gagal": {"debug", "error", "crash", "fail"},
    "kenapa": {"penyebab", "sebab", "cause", "akar", "masalah"},
    "rusak": {"error", "crash", "gagal", "debug", "bug"},
    "mati": {"crash", "gagal", "error", "debug"},
    # review / keamanan
    "review": {"kode", "kualitas", "bug", "keamanan", "quality"},
    "keamanan": {"security", "vulnerability", "aman", "exploit", "injection"},
    "security": {"keamanan", "vulnerability", "exploit", "injection"},
    "vulnerability": {"keamanan", "security", "exploit"},
    # kinerja
    "lambat": {"slow", "kinerja", "perf", "optimasi", "bottleneck"},
    "slow": {"lambat", "kinerja", "perf", "optimasi", "bottleneck"},
    "optimasi": {"optimize", "perf", "lambat", "kinerja", "bottleneck"},
    "kinerja": {"perf", "lambat", "slow", "optimasi"},
    # testing
    "test": {"testing", "pytest", "tdd", "unit"},
    "testing": {"test", "pytest", "tdd"},
    "pytest": {"test", "testing", "tdd"},
    # web & api
    "api": {"http", "rest", "endpoint", "request", "curl"},
    "http": {"api", "request", "endpoint", "curl", "rest"},
    "request": {"api", "http", "endpoint"},
    "cari": {"search", "internet", "web", "google"},
    "search": {"cari", "internet", "web"},
    # database
    "database": {"sql", "query", "db", "mysql", "postgres", "sqlite"},
    "sql": {"database", "query", "db", "mysql", "postgres"},
    "query": {"sql", "database", "db"},
    # memory
    "ingat": {"remember", "memory", "fakta"},
    "lupa": {"forget", "memory"},
    "memory": {"ingat", "remember", "fakta"},
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


def _kw_weighted_intersection(a: set[str], b: set[str]) -> int:
    """Kata langka (>= 6 huruf) berbobot 2 — sinyal lebih kuat daripada kata umum."""
    return sum(2 if len(k) >= 6 else 1 for k in a & b)


def _expand_aliases(kws: set[str]) -> set[str]:
    """Perluas kata kunci prompt lewat peta sinonim (crash → debug/error/...)."""
    out: set[str] = set()
    for k in kws:
        out |= ALIAS_EXPANSIONS.get(k, set())
    return out


def score_skill(sk: Skill, prompt_kw: set[str], history_kw: set[str] | None = None) -> int:
    """Skor relevansi skill terhadap prompt (dan riwayat sesi).

    - cocok kata kunci di prompt: ×2 (prompt adalah sinyal terkuat)
    - cocok kata kunci di riwayat sesi: ×1 (konteks percakapan)
    - cocok sinonim/alias prompt: ×2 (mis. 'crash' → konsep debugging)
    - nama skill ikut dihitung (user bisa mengetik 'pakai skill tdd')
    """
    dk = _keywords(sk.description) | _keywords(sk.name)
    score = 2 * _kw_weighted_intersection(dk, prompt_kw)
    if history_kw:
        score += _kw_weighted_intersection(dk, history_kw)
    score += 2 * _kw_weighted_intersection(dk, _expand_aliases(prompt_kw))
    return score


def select_skills(
    prompt: str,
    skills: list[Skill],
    history: str = "",
    force: list[str] | None = None,
    min_score: int = 1,
) -> list[str]:
    """Pilih skill relevan (urut skor turun); `force` selalu didahulukan.

    Return daftar nama skill yang LAYAK di-inject (belum dipotong max_inject).
    """
    pk = _keywords(prompt)
    hk = _keywords(history) if history else None
    forced = [f.lower() for f in (force or [])]
    by_name = {s.name: s for s in skills}

    forced_hits = [n for n in forced if n in by_name]
    rest: list[tuple[int, Skill]] = []
    # fuzzy matching (rapidfuzz): typo "debgu" → skill debugging tetap ketemu.
    # Graceful: kalau rapidfuzz tidak terpasang, jalan seperti dulu.
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None
    for sk in skills:
        if sk.name in forced_hits:
            continue
        sc = score_skill(sk, pk, hk)
        if _fuzz is not None:
            # typo karakter ("debuging" → debugging): partial_ratio pada NAMA;
            # kemiripan kalimat: token_set_ratio pada deskripsi.
            fb = max(
                _fuzz.ratio(prompt.lower(), sk.name),
                _fuzz.partial_ratio(prompt.lower(), sk.name),
                _fuzz.token_set_ratio(prompt.lower(), sk.description),
            )
            if sc >= min_score and fb >= 85:
                sc += 1  # relevan + mirip → prioritas naik
            elif sc < min_score and fb >= 75:
                sc = min_score  # typo/kemiripan → layak inject
        if sc >= min_score:
            rest.append((sc, sk))
    rest.sort(key=lambda x: -x[0])
    ordered = [by_name[n] for n in forced_hits] + [s for _, s in rest]
    return [s.name for s in ordered]


MENTION_RE = re.compile(r"@([a-z0-9][a-z0-9_-]*)", re.IGNORECASE)


def extract_skill_mentions(prompt: str, known: set[str]) -> tuple[str, list[str]]:
    """`@nama_skill` di prompt → (prompt bersih, daftar skill valid).

    Mention yang dikenal DIBUANG dari prompt (kontrol user, bukan teks model);
    @ yang tidak dikenal dibiarkan (bisa jadi username GitHub dll).
    """
    found: list[str] = []

    def _sub(m: re.Match) -> str:
        name = m.group(1).lower()
        if name in known:
            found.append(name)
            return ""
        return m.group(0)

    return MENTION_RE.sub(_sub, prompt), found


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


MUTATING_TOOLS = {"apply_patch", "write_file", "git_commit"}


def auto_skill_worthwhile(
    tools_used: list[str],
    tool_counts: dict[str, int] | None = None,
    final: str = "",
    files_created: int = 0,
    tests_passed: bool | None = None,
) -> bool:
    """Task nyata = ada KARYA nyata: file dibuat/diubah, test dijalankan, atau
    tool mutasi dipakai. Sesi tanya-jawab / eksplorasi (hanya ls/grep/read/fetch)
    TIDAK menghasilkan skill — cegah skill sampah seperti 'lanjutkan', 'hai'."""
    if not tools_used:
        return False
    if not final or final.startswith("[error"):
        return False
    if files_created > 0:
        return True
    if any(t in MUTATING_TOOLS for t in tools_used):
        return True
    return "run_tests" in tools_used


def inject_skills(
    prompt: str,
    skills: list[Skill],
    max_inject: int = 3,
    max_chars: int = 800,
    history: str = "",
    force: list[str] | None = None,
) -> str:
    """Tambahkan body skill yang relevan ke prompt (prefix).

    - relevansi: kata kunci prompt + riwayat sesi + sinonim (lihat select_skills)
    - `force`: nama skill yang WAJIB di-inject (didahulukan, dipakai /skill & @nama)
    """
    names = select_skills(prompt, skills, history=history, force=force)
    by_name = {s.name: s for s in skills}
    parts = []
    for n in names[:max_inject]:
        sk = by_name.get(n)
        if sk is None:
            continue
        parts.append(f"[SKILL: {sk.name}]\n{sk.body[:max_chars]}")
    if not parts:
        return prompt
    return "\n\n".join(parts) + "\n\n---\n\n" + prompt
