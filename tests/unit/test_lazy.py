from dhybrid.efficiency.lazy import (
    build_system_prompt,
    needs_change_check,
    summarize_diff_stat,
)


def test_system_prompt_contains_lazy_rules():
    p = build_system_prompt("Kamu adalah coding agent.", "~/proj")
    assert "ATURAN KERJA" in p
    assert "~/proj" in p
    assert p.count("ATURAN KERJA") == 1


def test_needs_change_signal():
    assert needs_change_check("Selesai. TIDAK ADA YANG PERLU DIUBAH.")
    assert not needs_change_check("Selesai, saya ubah 2 file.")


def test_summarize_diff_stat():
    stat = "src/a.py | 3 +--\n1 file changed, 2 insertions(+), 1 deletion(-)\n"
    out = summarize_diff_stat(stat)
    assert "src/a.py" in out and "1 file changed" not in out
    assert summarize_diff_stat("nothing") == "(tidak ada perubahan)"
