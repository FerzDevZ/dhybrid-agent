"""Deteksi intent prompt — kenali prompt ambigu/underspecified (murni heuristik,
tanpa biaya token LLM) dan siapkan opsi pilihan bernomor + default.

Dipakai REPL SEBELUM agent dipanggil: prompt seperti "buat web login register"
(yang tidak menyebut stack) → tampilkan pilihan (1. PHP/Laravel, 2. Next.js,
3. React+Vite, ...) supaya user tinggal jawab angka / teks bebas / "Lanjutkan".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from dhybrid.skills.loader import STOPWORDS

# Kata kerja MEMBANGUN — sinyal prompt ingin membuat sesuatu
BUILD_VERBS = {
    "buat", "bikin", "bangun", "buatin", "bikinin", "buatkan", "bikinkan",
    "kerjakan", "kerjain", "minta", "tolong", "bantu", "bantuin",
    "implementasikan", "implementasi", "buatkanlah", "ciptakan", "develop",
}

# Kata stack eksplisit — prompt yang menyebutnya dianggap JELAS (tidak ditanya)
STACK_WORDS = {
    "php", "laravel", "django", "flask", "rails", "ruby", "node", "nodejs",
    "next", "nextjs", "react", "vue", "svelte", "angular", "nuxt", "gatsby",
    "astro", "go", "golang", "rust", "java", "kotlin", "swift", "flutter",
    "reactnative", "react-native", "python", "typescript", "javascript", "js",
    "html", "css", "tailwind", "bootstrap", "sql", "mysql", "postgres",
    "postgresql", "sqlite", "mongodb", "docker", "fastapi", "express",
    "springboot", "spring", "wordpress", "codeigniter", "blade", "streamlit",
}

STACK_OPTIONS_WEB = ["PHP (Laravel)", "Next.js", "React + Vite", "Python (Django/Flask)"]
STACK_OPTIONS_CLI = ["Python", "Node.js", "Go", "Rust"]
STACK_OPTIONS_MOBILE = ["Flutter", "React Native", "Kotlin (Android)", "Swift (iOS)"]
STACK_OPTIONS_DEFAULT = ["Python", "PHP (Laravel)", "Next.js", "React + Vite"]

# kategori task → opsi stack populer
TASK_KINDS: list[tuple[set[str], list[str]]] = [
    (
        {"login", "register", "web", "landing", "page", "halaman", "crud",
         "situs", "website", "api", "dashboard", "frontend", "backend", "blog"},
        STACK_OPTIONS_WEB,
    ),
    (
        {"cli", "script", "tool", "otomasi", "automation", "scraping", "bot",
         "cron", "daemon", "utility", "scraper"},
        STACK_OPTIONS_CLI,
    ),
    (
        {"android", "ios", "mobile", "aplikasi", "app", "flutter", "hp"},
        STACK_OPTIONS_MOBILE,
    ),
]

# deteksi stack project di cwd → label opsi default
PROJECT_SIGNALS: list[tuple[tuple[str, ...], str]] = [
    (("composer.json",), "PHP (Laravel)"),
    (("package.json", "next.config.js"), "Next.js"),
    (("package.json", "next.config.ts"), "Next.js"),
    (("package.json", "vite.config.js"), "React + Vite"),
    (("package.json", "vite.config.ts"), "React + Vite"),
    (("pubspec.yaml",), "Flutter"),
    (("go.mod",), "Go"),
    (("Cargo.toml",), "Rust"),
    (("requirements.txt",), "Python"),
    (("pyproject.toml",), "Python"),
]


@dataclass
class ClarifyHint:
    """Saran pertanyaan klarifikasi: pilihan bernomor + default."""

    question: str
    options: list[str]
    default_index: int = 0
    confidence: float = 0.8
    meta: dict = field(default_factory=dict)


def _words(prompt: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9_]{2,}", prompt.lower()) if w not in STOPWORDS}


def detect_project_stack(cwd: str | None) -> str | None:
    """Deteksi stack project di cwd (composer.json → PHP/Laravel, dst)."""
    if not cwd:
        return None
    d = Path(cwd).expanduser()
    if not d.is_dir():
        return None
    for files, label in PROJECT_SIGNALS:
        if all((d / f).exists() for f in files):
            return label
    return None


def _options_for(words: set[str], proj: str | None) -> list[str]:
    """Opsi stack untuk kategori task; project di cwd jadi default (index 0)."""
    for kind_words, opts in TASK_KINDS:
        if words & kind_words:
            if proj:
                return [f"{proj} (proyek ini)"] + [o for o in opts if o != proj]
            return list(opts)
    if proj:
        return [f"{proj} (proyek ini)"] + [o for o in STACK_OPTIONS_DEFAULT if o != proj]
    return list(STACK_OPTIONS_DEFAULT)


def detect_ambiguity(
    prompt: str,
    cwd: str | None = None,
    history: str = "",
    last_turn_was_answer: bool = False,
) -> ClarifyHint | None:
    """Deteksi prompt ambigu/underspecified.

    Fire bila: ada kata kerja membangun + TIDAK ada stack eksplisit (di prompt
    maupun riwayat sesi terakhir) + bukan jawaban lanjutan. Return None bila
    prompt sudah jelas / sapaan / pertanyaan biasa.
    """
    if last_turn_was_answer:
        return None
    words = _words(prompt)
    if not (words & BUILD_VERBS):
        return None
    if words & STACK_WORDS:
        return None
    # stack sudah disebut di riwayat sesi (mis. "pakai laravel" turn lalu) →
    # prompt lanjutan dianggap jelas, jangan tanya lagi.
    if history and (_words(history) & STACK_WORDS):
        return None

    proj = detect_project_stack(cwd)
    options = _options_for(words, proj)
    question = "Task ini belum menyebut stack-nya. Mau pakai teknologi yang mana?"
    return ClarifyHint(
        question=question,
        options=options,
        default_index=0,
        confidence=0.8,
        meta={"project": proj or "", "words": sorted(words)},
    )
