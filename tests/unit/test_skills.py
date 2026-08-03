from dhybrid.skills.loader import inject_skills, list_skills

TDD_SKILL = """---
name: tdd
description: TDD test-driven development, red-green-refactor, tulis test dulu
---

TDD: tulis test dulu (RED), implementasi minimal (GREEN), refactor.
"""


def test_list_skills(tmp_path):
    d = tmp_path / "skills"
    (d / "tdd").mkdir(parents=True)
    (d / "tdd" / "SKILL.md").write_text(TDD_SKILL)
    skills = list_skills(d)
    assert len(skills) == 1
    assert skills[0].name == "tdd"
    assert "TDD:" in skills[0].body


def test_inject_relevant_skill_only(tmp_path):
    d = tmp_path / "skills"
    (d / "tdd").mkdir(parents=True)
    (d / "tdd" / "SKILL.md").write_text(TDD_SKILL)
    (d / "gaming").mkdir(parents=True)
    (d / "gaming" / "SKILL.md").write_text(
        "---\nname: gaming\ndescription: tips bermain game\n---\nGaming tips\n"
    )
    skills = list_skills(d)
    out = inject_skills("bantu saya pakai TDD untuk fitur ini", skills)
    assert "[SKILL: tdd]" in out
    assert "Gaming tips" not in out


def test_inject_returns_prompt_when_no_match():
    skills = []
    out = inject_skills("hello", skills)
    assert out == "hello"


def test_slugify_from_prompt():
    from dhybrid.skills.loader import slugify

    assert slugify("tolong perbaiki bug di file calc.py") == "perbaiki-bug-file"
    assert slugify("haloo?") == "haloo"  # stopword 'tolong' dibuang; tetap ada kata
    assert slugify("yang dan di ke") == "task"  # semua stopword → fallback


def test_auto_skill_worthwhile():
    from dhybrid.skills.loader import auto_skill_worthwhile

    # aksi mengubah file → layak
    assert auto_skill_worthwhile(["terminal", "apply_patch"], {"terminal": 3, "apply_patch": 1}, "selesai") is True
    # sapaan tanpa tool → tidak
    assert auto_skill_worthwhile([], {}, "halo") is False
    # error → tidak
    assert auto_skill_worthwhile(["terminal"], {"terminal": 2}, "[error API] x") is False
    # eksplorasi saja (ls/grep/read/fetch, tanpa ubah file) → TIDAK jadi skill,
    # berapa pun banyak tool yang dipakai (cegah skill sampah 'lanjutkan'/'hai')
    assert auto_skill_worthwhile(["terminal", "grep"], {"terminal": 1, "grep": 1}, "jawaban pertanyaan") is False
    assert auto_skill_worthwhile(["terminal", "grep"], {"terminal": 3, "grep": 2}, "hasil analisis") is False
    assert auto_skill_worthwhile(
        ["terminal", "git_status", "read_file", "find_files", "web_fetch"], {}, "dimana cek webnya"
    ) is False
    # file nyata dibuat → layak (mis. sesi lanjutan yang benar-benar mengerjakan)
    assert auto_skill_worthwhile(["terminal", "write_file"], {"terminal": 2, "write_file": 1}, "selesai", files_created=1) is True
    # test dijalankan → layak
    assert auto_skill_worthwhile(["terminal", "run_tests"], {"terminal": 1, "run_tests": 1}, "semua lulus") is True


def test_short_args_hides_content(tmp_path):
    """Indikator tool tidak boleh bocorkan isi write_file."""
    from dhybrid.ui.repl import _short_args

    out = _short_args({"path": "app.py", "content": "#!/usr/bin/env python3\n" + "x" * 500})
    assert "chars>" in out and "python3" not in out and "\n" not in out
    assert len(out) < 80


DEBUG_SKILL = """---
name: debugging
description: Debug error traceback, sistematis, cari akar masalah, jangan menebak
---

Debugging sistematis.
"""


def _skills_with(tmp_path, *skill_texts):
    from dhybrid.skills.loader import list_skills

    d = tmp_path / "skills"
    for i, text in enumerate(skill_texts):
        (d / f"sk{i}").mkdir(parents=True)
        (d / f"sk{i}" / "SKILL.md").write_text(text)
    return list_skills(d)


def test_alias_expansion_matches_debugging(tmp_path):
    """'program saya crash' (tanpa kata 'debug') tetap mencocokkan skill debugging."""
    from dhybrid.skills.loader import select_skills

    skills = _skills_with(tmp_path, DEBUG_SKILL, TDD_SKILL)
    names = select_skills("kenapa program saya crash terus", skills)
    assert "debugging" in names
    assert "tdd" not in names


def test_name_match_and_weighted_rare_word(tmp_path):
    """Menyebut nama skill di prompt langsung cocok; kata langka berbobot lebih."""
    from dhybrid.skills.loader import select_skills

    skills = _skills_with(tmp_path, TDD_SKILL)
    names = select_skills("pakai skill tdd untuk fitur ini", skills)
    assert names == ["tdd"]


def test_history_matching(tmp_path):
    """Skill cocok dari riwayat sesi: 'database' di awal → tetap relevan."""
    from dhybrid.skills.loader import select_skills

    db_skill = """---
name: database-query
description: Query SQL, index, explain, join, optimasi database
---

SQL.
"""
    skills = _skills_with(tmp_path, db_skill)
    # prompt sekarang tidak menyebut database, tapi riwayat menyebutnya
    names = select_skills("lanjutkan", skills, history="tadi kita bahas query database postgres")
    assert "database-query" in names
    # tanpa riwayat → tidak cocok
    assert select_skills("lanjutkan", skills) == []


def test_force_inject_even_without_match(tmp_path):
    """force (dari /skill atau @nama) tetap di-inject walau tanpa kata kunci cocok."""
    from dhybrid.skills.loader import inject_skills

    skills = _skills_with(tmp_path, TDD_SKILL)
    out = inject_skills("hello saja", skills, force=["tdd"])
    assert "[SKILL: tdd]" in out


def test_extract_skill_mentions():
    from dhybrid.skills.loader import extract_skill_mentions

    clean, found = extract_skill_mentions(
        "cek @debugging dan @Code-Review ini", {"debugging", "code-review"}
    )
    assert found == ["debugging", "code-review"]
    assert "debugging" not in clean and "Code-Review" not in clean
    # @ tidak dikenal → dibiarkan (bisa username GitHub)
    clean2, found2 = extract_skill_mentions("@github-user halo", {"debugging"})
    assert found2 == [] and "@github-user" in clean2


def test_select_skills_forced_first():
    from pathlib import Path

    from dhybrid.skills.loader import Skill, select_skills

    skills = [
        Skill("tdd", "TDD test-driven development", "TDD body", Path("x")),
        Skill("debugging", "Debug error traceback", "Debug body", Path("y")),
    ]
    names = select_skills("ada error di kode", skills, force=["tdd"])
    assert names[0] == "tdd"  # paksa didahulukan
    assert "debugging" in names  # relevan tetap ikut


def test_ask_user_non_interactive_blocked():
    from dhybrid.tools.ask import BLOCKED_SENTINEL, AskState, register
    from dhybrid.tools.registry import ToolRegistry

    state = AskState(interactive=False)
    reg = ToolRegistry()
    register(reg, state)
    out = reg.execute("ask_user", {"prompt": "pilih apa?"})
    assert out.startswith(BLOCKED_SENTINEL)
    assert state.pending is None  # tidak ada pertanyaan menggantung


def test_ask_user_pending_and_count_guard():
    from dhybrid.tools.ask import ASK_MAX, PENDING_SENTINEL, AskState, register
    from dhybrid.tools.registry import ToolRegistry

    state = AskState(interactive=True)
    reg = ToolRegistry()
    register(reg, state)
    for _ in range(ASK_MAX):
        out = reg.execute("ask_user", {"prompt": "q", "options": ["a", "b"]})
        assert out == PENDING_SENTINEL
        assert state.pending == {"prompt": "q", "options": ["a", "b"]}
        state.pending = None  # REPL mengambil & membersihkan
    # ke-3 diblokir → agent harus putuskan sendiri
    out = reg.execute("ask_user", {"prompt": "q lagi"})
    assert "BLOCKED" in out
    assert state.pending is None
    assert state.count == ASK_MAX


def test_slugify_fallback_generic():
    from dhybrid.skills.loader import slugify

    assert slugify("4") == "task"        # terlalu pendek → fallback generic
    assert slugify("123") == "123"       # numerik murni → skip di auto-learn (tanpa huruf)


def test_build_skill_md_compact_and_parsable(tmp_path):
    from dhybrid.skills.loader import build_skill_md, list_skills

    md = build_skill_md("fix-bug", "perbaiki bug", "perbaiki bug di calc", ["terminal", "patch"], "hasil ok", steps="1. pakai tool")
    (tmp_path / "fix-bug").mkdir()
    (tmp_path / "fix-bug" / "SKILL.md").write_text(md)
    skills = list_skills(tmp_path)
    assert skills[0].name == "fix-bug"
    assert len(md) < 600  # hemat token: skill otomatis harus ringkas


def test_skills_loaded_from_project_and_user_dirs(tmp_path):
    """SessionContext memuat skill proyek + skill user (~/.dhybrid/skills)."""
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    proj = tmp_path / "proj"
    (proj / "skills" / "aaa").mkdir(parents=True)
    (proj / "skills" / "aaa" / "SKILL.md").write_text(
        "---\nname: aaa\ndescription: skill proyek aaa\n---\nAaa\n"
    )
    user_skills = tmp_path / "home" / ".dhybrid" / "skills"
    (user_skills / "bbb").mkdir(parents=True)
    (user_skills / "bbb" / "SKILL.md").write_text(
        "---\nname: bbb\ndescription: skill user bbb\n---\nBbb\n"
    )
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path / "home" / ".dhybrid"
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(proj))
    names = {s.name for s in ctx.skills}
    assert "aaa" in names and "bbb" in names
    # skill BAWAAN (repo skills/) selalu tersedia di folder mana pun
    assert "tdd" in names and "debugging" in names and "lazy" in names


def test_disabled_skill_not_injected(tmp_path, monkeypatch):
    """Skill yang dimatikan user tidak ikut di-inject, tapi tetap terdaftar."""
    import dhybrid.session.userconfig as uc
    from dhybrid.config import Config
    from dhybrid.session.context import SessionContext
    from dhybrid.session.store import SessionStore

    monkeypatch.setattr(uc, "user_config_path", lambda: tmp_path / "config.yaml")
    uc.toggle_skill("debugging")
    cfg = Config.load("config/default.yaml")
    cfg.workspace = tmp_path / ".dhybrid"
    ctx = SessionContext(cfg, SessionStore(tmp_path / "s.sqlite"), cwd=str(tmp_path))
    assert "debugging" not in {s.name for s in ctx.skills}       # tidak di-inject
    assert "debugging" in {s.name for s in ctx.all_skills}       # tetap terdaftar
    assert "debugging" in ctx.disabled_skills
