"""Text-to-Tool-Call Parser untuk model free yang tidak support native tool calling.

Parse natural language output → extract intent → convert to tool calls.
Experimental wrapper untuk model free (Zen free models).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Pattern untuk mendeteksi intent coding di teks natural
FILE_CREATE_PATTERNS = [
    r"(?:buat|buatkan|bikin|create|make)\s+(?:file\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?\s*(?:dengan|berisi|isi)\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
    r"(?:tulis|tuliskan|write)\s+(?:ke\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?\s*[:：]\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
    r"(?:simpan|save)\s+(?:ke\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?\s*[:：]\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
]

FILE_READ_PATTERNS = [
    r"(?:baca|bacakah|read|lihat)\s+(?:file\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?",
    r"(?:tampilkan|show|cat)\s+(?:file\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?",
]

FILE_EDIT_PATTERNS = [
    r"(?:edit|ubah|ubah|ganti|replace|modify)\s+(?:file\s+)?[`\"']?([\w\/\.\-]+\.\w+)[`\"']?\s*(?:dengan|menjadi|to)\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
    r"(?:ganti|replace)\s+[`\"']?([\s\S]*?)[`\"']?\s+(?:dengan|menjadi|to)\s*[`\"']?([\s\S]*?)[`\"']?\s+(?:di|pada|in)\s+[`\"']?([\w\/\.\-]+\.\w+)[`\"']?",
]

COMMAND_PATTERNS = [
    r"(?:jalankan|run|execute|eksekusi)\s+(?:perintah|command)\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
    r"(?:terminal|shell|bash)\s*[`\"']?([\s\S]*?)[`\"']?(?:\s*$|\s*\.)",
]

GREP_PATTERNS = [
    r"(?:cari|search|grep|find)\s+[`\"']?([\s\S]*?)[`\"']?\s+(?:di|in|pada)\s+[`\"']?([\w\/\.\-]*)[`\"']?",
]

LIST_PATTERNS = [
    r"(?:list|ls|daftar)\s+(?:file\s+)?[`\"']?([\w\/\.\-]*)[`\"']?",
]

@dataclass
class ParsedToolCall:
    name: str
    arguments: dict
    confidence: float  # 0-1

class TextToToolParser:
    """Parse natural language text → tool calls untuk model free."""
    
    def __init__(self):
        self.patterns = [
            (FILE_CREATE_PATTERNS, "write_file", self._parse_write_file),
            (FILE_READ_PATTERNS, "read_file", self._parse_read_file),
            (FILE_EDIT_PATTERNS, "apply_patch", self._parse_apply_patch),
            (COMMAND_PATTERNS, "terminal", self._parse_terminal),
            (GREP_PATTERNS, "grep", self._parse_grep),
            (LIST_PATTERNS, "find_files", self._parse_find_files),
        ]
    
    def parse(self, text: str) -> list[ParsedToolCall]:
        """Parse teks natural language → list tool calls."""
        calls = []

        for patterns, tool_name, parser in self.patterns:
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                for match in matches:
                    try:
                        args = parser(match)
                        if args:
                            confidence = self._calculate_confidence(text, match, tool_name)
                            calls.append(ParsedToolCall(
                                name=tool_name,
                                arguments=args,
                                confidence=confidence
                            ))
                    except Exception:  # noqa: BLE001,S112 — lewati pattern yg gagal parse
                        continue
        
        # Sort by confidence descending
        calls.sort(key=lambda c: c.confidence, reverse=True)
        return calls
    
    def _calculate_confidence(self, text: str, match: re.Match, tool_name: str) -> float:
        """Hitung confidence berdasarkan konteks."""
        base = 0.6
        # Boost jika ada kata kunci eksplisit
        keywords = {
            "write_file": ["buat", "buatkan", "bikin", "create", "tulis", "simpan"],
            "read_file": ["baca", "read", "lihat", "tampilkan"],
            "apply_patch": ["edit", "ubah", "ganti", "replace", "modify"],
            "terminal": ["jalankan", "run", "execute", "terminal", "bash"],
            "grep": ["cari", "search", "grep", "find"],
            "find_files": ["list", "ls", "daftar"],
        }
        for kw in keywords.get(tool_name, []):
            if kw in match.group(0).lower():
                base += 0.1
        return min(base, 0.95)
    
    # Parser functions
    def _parse_write_file(self, match: re.Match) -> dict | None:
        groups = match.groups()
        if len(groups) >= 2:
            path = groups[0].strip().strip('`"\'')
            content = groups[1].strip().strip('`"\'')
            if path and content is not None:
                return {"path": path, "content": content}
        return None
    
    def _parse_read_file(self, match: re.Match) -> dict | None:
        groups = match.groups()
        if groups:
            path = groups[0].strip().strip('`"\'')
            if path:
                return {"path": path, "offset": 1, "limit": 100}
        return None
    
    def _parse_apply_patch(self, match: re.Match) -> dict | None:
        groups = match.groups()
        if len(groups) >= 2:
            path = groups[0].strip().strip('`"\'')
            new_content = groups[1].strip().strip('`"\'')
            if path:
                # For apply_patch we need old_content - approximate with placeholder
                return {"path": path, "old_string": "<<PLACEHOLDER>>", "new_string": new_content}
        return None
    
    def _parse_terminal(self, match: re.Match) -> dict | None:
        groups = match.groups()
        if groups:
            cmd = groups[0].strip().strip('`"\'')
            if cmd:
                return {"command": cmd}
        return None
    
    def _parse_grep(self, match: re.Match) -> dict | None:
        groups = match.groups()
        if len(groups) >= 1:
            pattern = groups[0].strip().strip('`"\'')
            path = groups[1].strip().strip('`"\'') if len(groups) > 1 else "."
            if pattern:
                return {"pattern": pattern, "path": path}
        return None
    
    def _parse_find_files(self, match: re.Match) -> dict | None:
        groups = match.groups()
        path = groups[0].strip().strip('`"\'') if groups else "."
        return {"path": path, "pattern": "*"}


def extract_tool_calls_from_text(text: str, min_confidence: float = 0.5) -> list[dict]:
    """Entry point: parse text → list tool call dicts.
    
    Supports two formats:
    1. Natural language: "buat file test.py dengan isi print('hello')"
    2. Legacy tool blocks: ```tool {"name": "grep", "arguments": {"q": "x"}} ```
    """
    # First try legacy tool block format
    from dhybrid.agent.parsing import dedupe_tool_calls, parse_tool_calls
    legacy_calls = dedupe_tool_calls(parse_tool_calls(text))
    if legacy_calls:
        return legacy_calls
    
    # Then try natural language parsing
    parser = TextToToolParser()
    calls = parser.parse(text)
    return [
        {"name": c.name, "arguments": c.arguments}
        for c in calls
        if c.confidence >= min_confidence
    ]


# Test
if __name__ == "__main__":
    test_cases = [
        "Buat file test.py dengan isi print('hello world')",
        "Baca file config.yaml",
        "Jalankan perintah python test.py",
        "Cari kata 'error' di folder src",
        "Edit file config.py ganti debug=true menjadi debug=false",
        "List file di folder src",
    ]
    
    for tc in test_cases:
        calls = extract_tool_calls_from_text(tc)
        print(f"Input: {tc}")
        for c in calls:
            print(f"  → {c['name']}({c['arguments']})")
        print()