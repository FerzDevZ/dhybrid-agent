"""Test tool code_map (tree-sitter AST) — python, php, javascript."""

from dhybrid.tools.code_map import code_map

PY = '''\
"""Modul contoh."""
import os


def main():
    return os.getcwd()


class User:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"halo {self.name}"
'''

PHP = """\
<?php
namespace App;

function helper() {
    return 1;
}

class UserController {
    public function index() {
        return 'ok';
    }
}
"""

JS = """\
export function add(a, b) {
    return a + b;
}

class Cart {
    constructor() {
        this.items = [];
    }
    total() {
        return this.items.length;
    }
}
"""


def test_code_map_python(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(PY)
    out = code_map(str(f))
    assert "code_map:" in out and "python" in out
    assert "fn main" in out
    assert "class User" in out
    assert "fn greet" in out


def test_code_map_php(tmp_path):
    f = tmp_path / "UserController.php"
    f.write_text(PHP)
    out = code_map(str(f))
    assert "fn helper" in out
    assert "class UserController" in out
    assert "fn index" in out


def test_code_map_javascript(tmp_path):
    f = tmp_path / "cart.js"
    f.write_text(JS)
    out = code_map(str(f))
    assert "fn add" in out
    assert "class Cart" in out
    assert "fn total" in out


def test_code_map_missing_file():
    out = code_map("/tidak/ada/file.py")
    assert out.startswith("ERROR")


def test_code_map_unsupported_extension(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    out = code_map(str(f))
    assert out.startswith("ERROR") and "lang=" in out


def test_code_map_no_symbols(tmp_path):
    f = tmp_path / "kosong.py"
    f.write_text("x = 1\n")
    out = code_map(str(f))
    assert "tidak ada fungsi/class" in out
