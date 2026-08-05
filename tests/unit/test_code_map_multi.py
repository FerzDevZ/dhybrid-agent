"""Tests for multi-language code map (Go, Rust, TypeScript, Java, C#)."""

from dhybrid.tools.code_map_multi import SUPPORTED_LANGUAGES, extract_symbols


def test_code_map_go_extracts_functions():
    go_code = "package main\nfunc Hello() string { return \"world\" }"
    symbols = extract_symbols("test.go", go_code, "go")
    assert any(s["name"] == "Hello" and s["kind"] == "function" for s in symbols)


def test_code_map_rust_extracts_functions():
    rust_code = "fn main() { println!(\"hello\"); }"
    symbols = extract_symbols("test.rs", rust_code, "rust")
    assert any(s["name"] == "main" and s["kind"] == "function" for s in symbols)


def test_code_map_typescript_extracts_functions():
    ts_code = "export function greet(name: string): string { return `Hello, ${name}`; }"
    symbols = extract_symbols("test.ts", ts_code, "typescript")
    assert any(s["name"] == "greet" and s["kind"] == "function" for s in symbols)


def test_code_map_java_extracts_methods():
    java_code = "public class Test { public void hello() { System.out.println(\"hi\"); } }"
    symbols = extract_symbols("Test.java", java_code, "java")
    assert any(s["name"] == "hello" and s["kind"] == "method" for s in symbols)


def test_code_map_csharp_extracts_methods():
    cs_code = "public class Test { public string Hello() { return \"world\"; } }"
    symbols = extract_symbols("Test.cs", cs_code, "c_sharp")
    assert any(s["name"] == "Hello" and s["kind"] == "method" for s in symbols)


def test_code_map_unsupported_language_returns_empty():
    symbols = extract_symbols("test.xyz", "code", "unsupported")
    assert symbols == []


def test_supported_languages_includes_all_five():
    assert "go" in SUPPORTED_LANGUAGES
    assert "rust" in SUPPORTED_LANGUAGES
    assert "typescript" in SUPPORTED_LANGUAGES
    assert "java" in SUPPORTED_LANGUAGES
    assert "c_sharp" in SUPPORTED_LANGUAGES