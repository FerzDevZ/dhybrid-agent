"""Multi-language AST-based code symbol extraction using Tree-sitter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tree_sitter

# Import language grammars
try:
    import tree_sitter_go as tsgo
    _go_language = tsgo.language
except ImportError:
    tsgo = None
    _go_language = None
try:
    import tree_sitter_rust as tsrust
    _rust_language = tsrust.language
except ImportError:
    tsrust = None
    _rust_language = None
try:
    import tree_sitter_typescript as tsts
    _typescript_language = tsts.language_typescript
except ImportError:
    tsts = None
    _typescript_language = None
try:
    import tree_sitter_java as tsjava
    _java_language = tsjava.language
except ImportError:
    tsjava = None
    _java_language = None
try:
    import tree_sitter_c_sharp as tscs
    _csharp_language = tscs.language
except ImportError:
    tscs = None
    _csharp_language = None


SUPPORTED_LANGUAGES = {
    "go": _go_language,
    "rust": _rust_language,
    "typescript": _typescript_language,
    "java": _java_language,
    "c_sharp": _csharp_language,
}

# Node types that define symbols for each language
SYMBOL_NODE_TYPES = {
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
    },
    "rust": {
        "function_item": "function",
    },
    "typescript": {
        "function_declaration": "function",
        "method_definition": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
    "java": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
    "c_sharp": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
}

# Wrapper node types that contain symbol nodes (e.g., export_statement in TypeScript)
WRAPPER_NODE_TYPES = {
    "typescript": {"export_statement"},
    "go": set(),
    "rust": set(),
    "java": set(),
    "c_sharp": set(),
}

# For each language, which child node contains the name
NAME_CHILD_TYPES = {
    "go": {"function_declaration": "identifier", "method_declaration": "field_identifier"},
    "rust": {"function_item": "identifier"},
    "typescript": {
        "function_declaration": "identifier",
        "method_definition": "property_identifier",
        "class_declaration": "type_identifier",
        "interface_declaration": "type_identifier",
    },
    "java": {
        "method_declaration": "identifier",
        "class_declaration": "identifier",
        "interface_declaration": "identifier",
    },
    "c_sharp": {
        "method_declaration": "identifier",
        "class_declaration": "identifier",
        "interface_declaration": "identifier",
    },
}


@dataclass
class Symbol:
    name: str
    kind: str
    line: int
    column: int


def _get_parser(lang: str) -> tree_sitter.Parser | None:
    """Get a tree-sitter parser for the given language."""
    lang_func = SUPPORTED_LANGUAGES.get(lang)
    if lang_func is None:
        return None
    try:
        language = tree_sitter.Language(lang_func())
        return tree_sitter.Parser(language)
    except (AttributeError, TypeError, ValueError):
        return None


def _find_name_child(node: tree_sitter.Node, lang: str, node_type: str) -> tree_sitter.Node | None:
    """Find the child node that contains the symbol name."""
    name_type = NAME_CHILD_TYPES.get(lang, {}).get(node_type)
    if not name_type:
        return None

    for child in node.children:
        if child.type == name_type:
            return child
    return None


def _walk_and_extract(node: tree_sitter.Node, lang: str, symbols: list[Symbol]) -> None:
    """Walk the AST and extract symbols."""
    node_types = SYMBOL_NODE_TYPES.get(lang, {})
    wrapper_types = WRAPPER_NODE_TYPES.get(lang, set())

    # Check if this is a wrapper node (e.g., export_statement)
    if node.type in wrapper_types:
        # Recurse into children to find the actual symbol nodes
        for child in node.children:
            _walk_and_extract(child, lang, symbols)
        return

    kind = node_types.get(node.type)
    if kind:
        name_node = _find_name_child(node, lang, node.type)
        if name_node:
            symbols.append(Symbol(
                name=name_node.text.decode("utf-8", errors="replace"),
                kind=kind,
                line=name_node.start_point[0] + 1,
                column=name_node.start_point[1],
            ))

    for child in node.children:
        _walk_and_extract(child, lang, symbols)


def extract_symbols(path: str, code: str, lang: str) -> list[dict[str, Any]]:
    """Extract symbols (functions, classes, etc.) from source code.

    Args:
        path: File path (used for context)
        code: Source code content
        lang: Language identifier (go, rust, typescript, java, c_sharp)

    Returns:
        List of symbol dicts with keys: name, kind, line, column
    """
    parser = _get_parser(lang)
    if parser is None:
        return []

    tree = parser.parse(code.encode())
    symbols: list[Symbol] = []
    _walk_and_extract(tree.root_node, lang, symbols)
    return [
        {"name": s.name, "kind": s.kind, "line": s.line, "column": s.column}
        for s in symbols
    ]


def get_supported_languages() -> list[str]:
    """Return list of supported language identifiers."""
    return [k for k, v in SUPPORTED_LANGUAGES.items() if v is not None]


_EXT_LANG = {
    ".go": "go",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cs": "c_sharp",
}


def code_map_multi(path: str, lang: str | None = None) -> str:
    """List functions/classes in a source file (AST tree-sitter) + line ranges.

    Supports: Go, Rust, TypeScript, Java, C#.

    Args:
        path: file path (relative to cwd or absolute).
        lang: go | rust | typescript | java | c_sharp. If empty, detected from extension.
    """
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return f"ERROR: file not found: {path}"
    size = p.stat().st_size
    if size > 2_000_000:  # 2MB
        return f"ERROR: file too large ({size // 1024}KB > 2MB) — not normal code"
    if not lang:
        lang = _EXT_LANG.get(p.suffix.lower())
        if not lang:
            return (
                f"ERROR: extension {p.suffix or '(no extension)'} not supported — "
                "specify lang= (go|rust|typescript|java|c_sharp)"
            )
    try:
        symbols = extract_symbols(str(p), p.read_text(encoding="utf-8", errors="replace"), lang)
    except RuntimeError as e:
        return f"ERROR: {e}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR parse {path}: {type(e).__name__}: {e}"

    if not symbols:
        return f"code_map_multi: {path} ({lang}) — no functions/classes found"

    kind_labels = {
        "function": "fn",
        "method": "method",
        "class": "class",
        "interface": "interface",
    }
    lines = [f"code_map_multi: {path} ({lang}) — {len(symbols)} symbols:"]
    for s in sorted(symbols, key=lambda x: x["line"]):
        label = kind_labels.get(s["kind"], s["kind"])
        lines.append(f"  {label} {s['name']} :{s['line']}")
    return "\n".join(lines)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "code_map_multi",
        "Multi-language code structure map (AST tree-sitter): list functions/classes + line ranges per file — "
        "go, rust, typescript, java, c_sharp. Token-efficient: see map first, read only relevant parts.",
        {"path": {"type": "string", "required": True}, "lang": {"type": "string"}},
        code_map_multi,
    )