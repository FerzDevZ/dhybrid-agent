"""Tests for dependency graph tool."""
from dhybrid.tools.dep_graph import SUPPORTED_LANGUAGES, build_dependency_graph


def test_dep_graph_python_imports():
    files = {
        "a.py": "import b",
        "b.py": "import c",
        "c.py": "",
    }
    graph = build_dependency_graph(files, "python")
    assert graph["a.py"] == ["b.py"]
    assert graph["b.py"] == ["c.py"]
    assert graph["c.py"] == []


def test_dep_graph_javascript_imports():
    files = {
        "a.js": "import './b'",
        "b.js": "import './c'",
        "c.js": "",
    }
    graph = build_dependency_graph(files, "javascript")
    assert graph["a.js"] == ["b.js"]
    assert graph["b.js"] == ["c.js"]


def test_dep_graph_go_imports():
    files = {
        "main.go": "package main\nimport \"github.com/user/proj/pkg\"\n",
        "pkg/pkg.go": "package pkg",
    }
    graph = build_dependency_graph(files, "go")
    # Go imports are package-based, not file-based
    assert "main.go" in graph


def test_dep_graph_rust_imports():
    files = {
        "main.rs": "mod foo;\nuse crate::foo::bar;",
        "foo.rs": "pub mod bar { pub fn baz() {} }",
    }
    graph = build_dependency_graph(files, "rust")
    assert "main.rs" in graph


def test_dep_graph_typescript_imports():
    files = {
        "a.ts": "import { foo } from './b'",
        "b.ts": "export const foo = 1",
    }
    graph = build_dependency_graph(files, "typescript")
    assert graph["a.ts"] == ["b.ts"]


def test_dep_graph_unsupported_language():
    graph = build_dependency_graph({"a.xyz": "code"}, "unsupported")
    assert graph == {"a.xyz": []}


def test_supported_languages():
    assert "python" in SUPPORTED_LANGUAGES
    assert "javascript" in SUPPORTED_LANGUAGES
    assert "typescript" in SUPPORTED_LANGUAGES
    assert "go" in SUPPORTED_LANGUAGES
    assert "rust" in SUPPORTED_LANGUAGES
    assert "java" in SUPPORTED_LANGUAGES
    assert "c_sharp" in SUPPORTED_LANGUAGES