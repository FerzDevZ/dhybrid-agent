"""Test intent.py — deteksi prompt ambigu + opsi stack + deteksi project cwd."""

from dhybrid.agent.intent import detect_ambiguity


def test_detect_ambiguity_web_app():
    h = detect_ambiguity("buat web login register")
    assert h is not None
    assert any("PHP" in o for o in h.options)
    assert any("Next.js" in o for o in h.options)
    assert 0 <= h.default_index < len(h.options)


def test_detect_ambiguity_explicit_stack():
    assert detect_ambiguity("buat web login pakai laravel") is None
    assert detect_ambiguity("buat web login dengan next js") is None
    assert detect_ambiguity("buat web login react vite") is None


def test_detect_ambiguity_smalltalk():
    assert detect_ambiguity("halo") is None
    assert detect_ambiguity("terima kasih") is None
    assert detect_ambiguity("ya") is None


def test_detect_ambiguity_question_without_build_verb():
    assert detect_ambiguity("apa itu laravel?") is None


def test_detect_ambiguity_project_context_laravel(tmp_path):
    (tmp_path / "composer.json").write_text("{}")
    h = detect_ambiguity("buat halaman login", cwd=str(tmp_path))
    assert h is not None
    assert h.options[0].startswith("PHP")
    assert h.default_index == 0


def test_detect_ambiguity_project_context_nextjs(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "next.config.js").write_text("")
    h = detect_ambiguity("buat halaman login", cwd=str(tmp_path))
    assert h is not None
    assert "Next.js" in h.options[0]
    assert h.default_index == 0


def test_detect_ambiguity_project_context_flutter(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: app")
    h = detect_ambiguity("bikin aplikasi android", cwd=str(tmp_path))
    assert h is not None
    assert "Flutter" in h.options[0]
    assert h.default_index == 0


def test_detect_ambiguity_skipped_after_answer():
    assert detect_ambiguity("buat web login", last_turn_was_answer=True) is None


def test_detect_ambiguity_history_knows_stack():
    # user pernah bilang "pakai laravel" → prompt berikutnya tidak ditanya lagi
    assert detect_ambiguity("buat halaman loginnya", history="oke pakai laravel saja") is None


def test_detect_ambiguity_cli():
    h = detect_ambiguity("bikin script otomasi")
    assert h is not None
    assert any("Python" in o for o in h.options)


def test_detect_ambiguity_short_ambiguous_prompt():
    h = detect_ambiguity("buat aplikasi")
    assert h is not None
