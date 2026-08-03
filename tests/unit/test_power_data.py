"""Task 5: tool data_query — SQL read-only ke CSV/JSONL via duckdb."""
from dhybrid.tools import power_data


def test_data_query_csv(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("nama,umur\nAndi,20\nBudi,30\n")
    out = power_data._data_query(f"SELECT * FROM read_csv_auto('{f}') WHERE umur > 25")
    assert "Budi" in out and "Andi" not in out


def test_data_query_jsonl(tmp_path):
    f = tmp_path / "data.jsonl"
    f.write_text('{"a": 1}\n{"a": 2}\n')
    out = power_data._data_query(f"SELECT sum(a) AS total FROM read_json_auto('{f}')")
    assert "3" in out


def test_data_query_blocks_write():
    out = power_data._data_query("CREATE TABLE x AS SELECT 1")
    assert "ERROR" in out
    out2 = power_data._data_query("SELECT 1; DROP TABLE x")
    assert "ERROR" in out2


def test_data_query_errors_gracefully():
    out = power_data._data_query("SELECT * FROM tidak_ada")
    assert "ERROR" in out
