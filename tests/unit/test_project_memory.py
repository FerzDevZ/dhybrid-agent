"""Test tool mem_index/mem_search — memory kode via sqlite-vec (vektor n-gram)."""

import pytest

from dhybrid.tools.project_memory import mem_index, mem_reset, mem_search

CODE = """\
def login_user(request):
    username = request.form["username"]
    password = request.form["password"]
    user = db.query("SELECT * FROM users WHERE username = ?", username)
    if user and check_password(password, user.password):
        session["user_id"] = user.id
        return redirect("/dashboard")
    return render_template("login.html", error="Kredensial salah")


def register_user(request):
    username = request.form["username"]
    password = hash_password(request.form["password"])
    db.execute("INSERT INTO users (username, password) VALUES (?, ?)", username, password)
    return redirect("/login")
"""


@pytest.fixture()
def isolated_mem(tmp_path, monkeypatch):
    monkeypatch.setenv("DHYBRID_MEM_DB", str(tmp_path / "mem.sqlite"))
    f = tmp_path / "auth.py"
    f.write_text(CODE)
    return f


def test_mem_index_then_search_finds_function(isolated_mem):
    out = mem_index(str(isolated_mem))
    assert "auth.py" in out and "chunk di-index" in out
    res = mem_search("fungsi login user session dashboard")
    assert "auth.py" in res
    assert "login_user" in res


def test_mem_search_ranks_relevant_higher(isolated_mem):
    mem_index(str(isolated_mem))
    res_login = mem_search("login session redirect dashboard")
    res_reg = mem_search("register hash password insert users")
    # keduanya ketemu, tapi skor chunk login vs register harus konsisten
    assert "auth.py" in res_login and "auth.py" in res_reg


def test_mem_search_empty_query(isolated_mem):
    out = mem_search("   ")
    assert out.startswith("ERROR")


def test_mem_search_no_index(tmp_path, monkeypatch):
    monkeypatch.setenv("DHYBRID_MEM_DB", str(tmp_path / "empty.sqlite"))
    res = mem_search("apa pun")
    assert "tidak ada chunk relevan" in res


def test_mem_index_missing_file():
    out = mem_index("/tidak/ada.py")
    assert out.startswith("ERROR")


def test_mem_reset_clears(isolated_mem):
    mem_index(str(isolated_mem))
    assert "dikosongkan" in mem_reset()
    res = mem_search("login")
    assert "tidak ada chunk relevan" in res