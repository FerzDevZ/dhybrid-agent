"""Dependency graph extraction using Tree-sitter for multiple languages."""

from __future__ import annotations

import tree_sitter

# Import language grammars
try:
    import tree_sitter_python as tspy
    _python_language = tspy.language
except ImportError:
    _python_language = None
try:
    import tree_sitter_javascript as tsjs
    _javascript_language = tsjs.language
except ImportError:
    _javascript_language = None
try:
    import tree_sitter_typescript as tsts
    _typescript_language = tsts.language_typescript
except ImportError:
    _typescript_language = None
try:
    import tree_sitter_go as tsgo
    _go_language = tsgo.language
except ImportError:
    _go_language = None
try:
    import tree_sitter_rust as tsrust
    _rust_language = tsrust.language
except ImportError:
    _rust_language = None
try:
    import tree_sitter_java as tsjava
    _java_language = tsjava.language
except ImportError:
    _java_language = None
try:
    import tree_sitter_c_sharp as tscs
    _csharp_language = tscs.language
except ImportError:
    _csharp_language = None


SUPPORTED_LANGUAGES = {
    "python": _python_language,
    "javascript": _javascript_language,
    "typescript": _typescript_language,
    "go": _go_language,
    "rust": _rust_language,
    "java": _java_language,
    "c_sharp": _csharp_language,
}

# Import patterns for each language
IMPORT_QUERIES = {
    "python": """
        (import_statement (dotted_name) @module)
        (import_statement (aliased_import (dotted_name) @module))
        (import_from_statement (dotted_name) @module)
    """,
    "javascript": """
        (import_statement (string) @module)
        (call_expression
            function: (identifier) @func (#eq? @func "require")
            arguments: (arguments (string) @module))
    """,
    "typescript": """
        (import_statement (string) @module)
    """,
    "go": """
        (import_spec
            (interpreted_string_literal) @module)
        (import_declaration
            (import_spec_list
                (import_spec
                    (interpreted_string_literal) @module)))
    """,
    "rust": """
        (use_declaration
            (use_tree
                (scoped_identifier
                    path: (identifier) @module)
                (identifier) @name))
        (use_declaration
            (use_tree
                (identifier) @module))
    """,
    "java": """
        (import_declaration
            (scoped_identifier) @module)
    """,
    "c_sharp": """
        (using_directive
            (qualified_name) @module)
    """,
}


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


def _get_language(lang: str) -> tree_sitter.Language | None:
    """Get a tree-sitter Language object for the given language."""
    lang_func = SUPPORTED_LANGUAGES.get(lang)
    if lang_func is None:
        return None
    try:
        return tree_sitter.Language(lang_func())
    except (AttributeError, TypeError, ValueError):
        return None


def _extract_imports(code: str, lang: str) -> list[str]:
    """Extract import module names from source code."""
    parser = _get_parser(lang)
    language = _get_language(lang)
    if parser is None or language is None:
        return []

    query_str = IMPORT_QUERIES.get(lang)
    if not query_str:
        return []

    try:
        query = tree_sitter.Query(language, query_str)
    except (ValueError, RuntimeError):
        return []

    tree = parser.parse(code.encode())
    cursor = tree_sitter.QueryCursor(query)
    captures = cursor.captures(tree.root_node)

    imports = []
    for capture_name, nodes in captures.items():
        if capture_name == "module":
            for node in nodes:
                if node is None:
                    continue
                text = node.text.decode("utf-8", errors="replace")
                text = text.strip('"\'`')
                if text:
                    imports.append(text)

    return list(set(imports))  # deduplicate


def _resolve_import_to_file(import_name: str, files: dict[str, str], lang: str, importing_file: str) -> str | None:
    """Resolve an import name to a file in the given file set."""
    # Simple resolution: convert module path to file path
    # This is a basic implementation - could be enhanced
    
    # Python: a.b.c -> a/b/c.py
    if lang == "python":
        path = import_name.replace(".", "/") + ".py"
        if path in files:
            return path
        # Try with __init__.py
        init_path = import_name.replace(".", "/") + "/__init__.py"
        if init_path in files:
            return init_path
    
    # JavaScript/TypeScript: ./foo or ../foo or foo
    elif lang in ("javascript", "typescript"):
        # Relative imports
        if import_name.startswith("."):
            # Resolve relative to importing file
            import os
            importing_dir = os.path.dirname(importing_file)
            if importing_dir:
                resolved = os.path.normpath(os.path.join(importing_dir, import_name))
            else:
                resolved = import_name.lstrip("./")
            
            # Try with extensions
            for ext in [".js", ".ts", "/index.js", "/index.ts"]:
                path = resolved + ext
                if path in files:
                    return path
            # Also try without extension
            if resolved in files:
                return resolved
        else:
            # Package import - check if it's a local file
            path = import_name + ".js"
            if path in files:
                return path
            path = import_name + ".ts"
            if path in files:
                return path
            path = import_name + "/index.js"
            if path in files:
                return path
    
    # Go: package imports (not file-based)
    elif lang == "go":
        pass  # Go uses package names, not file paths
    
    # Rust: crate::module
    elif lang == "rust":
        pass
    
    # Java: package imports
    elif lang == "java":
        path = import_name.replace(".", "/") + ".java"
        if path in files:
            return path
    
    # C#: namespace imports
    elif lang == "c_sharp":
        pass
    
    return None


def build_dependency_graph(files: dict[str, str], lang: str) -> dict[str, list[str]]:
    """Build a dependency graph from a set of files.

    Args:
        files: Dict mapping file paths to source code
        lang: Language identifier (python, javascript, typescript, go, rust, java, c_sharp)

    Returns:
        Dict mapping each file to a list of files it depends on
    """
    graph: dict[str, list[str]] = {path: [] for path in files}

    for path, code in files.items():
        imports = _extract_imports(code, lang)
        dependencies = []
        for imp in imports:
            resolved = _resolve_import_to_file(imp, files, lang, path)
            if resolved:
                dependencies.append(resolved)
        graph[path] = dependencies

    return graph


def dep_graph_tool(workspace: str, lang: str | None = None) -> str:
    """Build a dependency graph for all source files in a workspace.

    Args:
        workspace: Path to workspace directory
        lang: Language identifier (python, javascript, typescript, go, rust, java, c_sharp)
    """
    from pathlib import Path

    ws_path = Path(workspace)
    if not ws_path.is_dir():
        return f"ERROR: workspace not found: {workspace}"

    # Detect language from file extensions if not specified
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cs": "c_sharp",
    }

    if lang is None:
        # Find first source file to detect language
        for ext, l in ext_to_lang.items():
            if list(ws_path.rglob(f"*{ext}")):
                lang = l
                break
        if lang is None:
            return "ERROR: no supported source files found in workspace"

    # Collect all source files
    files = {}
    for ext, l in ext_to_lang.items():
        if l == lang:
            for f in ws_path.rglob(f"*{ext}"):
                if f.is_file():
                    try:
                        rel = f.relative_to(ws_path)
                        files[str(rel)] = f.read_text(encoding="utf-8", errors="replace")
                    except (OSError, UnicodeDecodeError):
                        pass

    if not files:
        return f"ERROR: no {lang} files found in workspace"

    graph = build_dependency_graph(files, lang)

    lines = [f"Dependency graph ({lang}) — {len(graph)} files:"]
    for src, deps in sorted(graph.items()):
        if deps:
            lines.append(f"  {src} -> {', '.join(deps)}")
        else:
            lines.append(f"  {src} (no deps)")
    return "\n".join(lines)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "dep_graph",
        "Build dependency graph for a workspace (AST tree-sitter): shows file imports/dependencies — "
        "python, javascript, typescript, go, rust, java, c_sharp. Token-efficient: see graph first.",
        {"workspace": {"type": "string", "required": True}, "lang": {"type": "string"}},
        dep_graph_tool,
    )