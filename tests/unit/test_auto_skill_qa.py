"""Task 9: auto-skill pengetahuan dari Q&A berulang (rapidfuzz ≥85%)."""
from dhybrid.skills.loader import build_skill_md
from dhybrid.ui.repl import _auto_learn_skill, _is_repeated_question_prompt


def test_qa_repeat_detection():
    assert _is_repeated_question_prompt("apa itu laravel", ["apa itu laravel?"]) is True
    assert _is_repeated_question_prompt("buat web", ["apa itu laravel?"]) is False


def test_qa_near_repeat_detection():
    assert (
        _is_repeated_question_prompt(
            "bagaimana cara install breeze", ["cara install breeze laravel"]
        )
        is True
    )


def test_knowledge_skill_md():
    md = build_skill_md(
        "apa-itu-laravel",
        "tentang laravel",
        "apa itu laravel?",
        ["web_search"],
        "Laravel adalah framework PHP yang populer.",
        kind="knowledge",
    )
    assert "Jawaban dari sesi nyata" in md and "Laravel" in md


def test_repeated_qa_creates_knowledge_skill(tmp_path, monkeypatch):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.qa_history = ["apa itu laravel?"]
    ctx.tools.tool_count = {"web_search": 1}
    result = _stub_result()
    result.final_text = (
        "Laravel adalah framework PHP untuk web. Ia menyediakan routing, "
        "blade templating, eloquent ORM, dan banyak komponen bawaan lainnya "
        "sehingga pengembangan web jadi cepat dan terstruktur."
    )
    _auto_learn_skill(ctx, "apa itu laravel?", result.final_text, result)
    target = ctx.workspace / "skills" / "apa-laravel" / "SKILL.md"
    assert target.exists()
    assert "Jawaban dari sesi nyata" in target.read_text()


def test_one_off_qa_does_not_create_skill(tmp_path, monkeypatch):
    ctx, _, _ = _make_ctx(tmp_path, monkeypatch)
    ctx.qa_history = ["apa itu laravel?"]
    ctx.tools.tool_count = {"web_search": 1}
    result = _stub_result()
    result.final_text = "Laravel adalah framework PHP untuk web yang bagus."
    _auto_learn_skill(ctx, "apa itu flutter?", result.final_text, result)
    assert not list((ctx.workspace / "skills").glob("*/SKILL.md"))


from tests.unit.test_repl_clarify import _make_ctx, _stub_result
