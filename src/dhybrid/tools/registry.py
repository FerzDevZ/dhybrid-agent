"""ToolRegistry — daftar tool + eksekusi dengan allowlist & error handling."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import chdir
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dhybrid.tools.validate import validate_args

# ---- JIT Tool Loading ----
# Alih-alih meng-inject SEMUA tool (~100) tiap prompt (boros token), hanya tool
# yang relevan dengan intent prompt yang di-render. CORE selalu ikut, kelompok
# lain dipilih via keyword (substring, ID/EN). Fallback aman: spec_text().
_CORE_TOOLS = {
    "terminal",
    "read_file",
    "write_file",
    "apply_patch",
    "grep",
    "find_files",
    "ask_user",
    "clarify",
    "sys_info",
    "run_bg",
    "poll_bg",
}
_TOOL_GROUPS: dict[str, tuple[frozenset[str], tuple[str, ...]]] = {
    "git": (
        frozenset({"git_status", "git_diff", "git_commit", "git_log"}),
        ("git", "commit", "branch", "push", "pull", "repo"),
    ),
    "todo": (
        frozenset({"todo_add", "todo_list", "todo_done", "todo_clear"}),
        ("todo",),
    ),
    "testing": (
        frozenset({"run_tests", "tdd_status"}),
        ("test", "pytest", "unittest", "tdd"),
    ),
    "memory": (
        frozenset(
            {
                "memory_set",
                "memory_get",
                "memory_search",
                "mem_index",
                "mem_search",
                "mem_reset",
                "episodic_remember",
                "episodic_recall",
                "episodic_recent",
                "episodic_forget",
            }
        ),
        ("ingat", "ingatkan", "memori", "memory", "kenang"),
    ),
    "subagents": (
        frozenset({"subagent", "orchestrator"}),
        ("subagent", "delegasi", "orchestrator", "bagi tugas"),
    ),
    "web": (
        frozenset({"web_fetch", "web_search", "http_request", "browser", "data_query"}),
        (
            "web",
            "website",
            "url",
            "http",
            "internet",
            "online",
            "scrape",
            "download",
            "fetch",
        ),
    ),
    "docs": (
        frozenset({"read_document", "pdf_ops", "xlsx_edit"}),
        ("pdf", "xlsx", "excel", "dokumen", "document", "docx"),
    ),
    "codegen": (
        frozenset({"codegen_openapi", "codegen_graphql", "codegen_protobuf"}),
        ("openapi", "swagger", "graphql", "protobuf"),
    ),
    "repo": (
        frozenset({"repo_issue", "repo_issues", "repo_pr"}),
        ("issue", "pull request", "pull-request", "pr github", "repo github", "github issue", "gitlab issue"),
    ),
    "scaffold": (
        frozenset({"scaffold"}),
        ("scaffold", "struktur proyek", "buat proyek", "inisialisasi proyek", "boilerplate"),
    ),
    "ci_cd": (frozenset({"ci_cd"}), ("ci/cd", "pipeline", "deploy")),
    "vision": (frozenset({"read_image"}), ("gambar", "image", "screenshot", "foto")),
    "explore": (
        frozenset(
            {"code_map", "code_map_multi", "dep_graph", "semantic_search", "git_log"}
        ),
        (
            "cek",
            "lihat",
            "baca",
            "eksplor",
            "explore",
            "cari",
            "temukan",
            "dimana",
            "bagaimana",
            "struktur",
            "jelaskan",
            "kenapa",
            "analisis",
            "inspeksi",
        ),
    ),
    "go": (
        frozenset(
            {
                "go_test",
                "go_vet",
                "go_fmt",
                "go_build",
                "go_mod_tidy",
                "golangci_lint",
                "gosec",
            }
        ),
        ("golang", "go module", "go test"),
    ),
    "rust": (
        frozenset(
            {
                "cargo_test",
                "cargo_build",
                "cargo_check",
                "cargo_fmt",
                "cargo_clippy",
                "cargo_audit",
                "cargo_update",
                "cargo_outdated",
            }
        ),
        ("cargo", "rust"),
    ),
    "node": (
        frozenset(
            {
                "npm_test",
                "npm_build",
                "npm_install",
                "npm_audit",
                "tsc_check",
                "eslint_check",
                "jest_test",
                "vitest_test",
                "prettier_fmt",
            }
        ),
        (
            "npm",
            "node",
            "typescript",
            "tsc",
            "javascript",
            "jsx",
            "react",
            "next.js",
            "nextjs",
            "eslint",
            "jest",
            "vitest",
            "webpack",
            "vite",
        ),
    ),
    "java": (
        frozenset(
            {
                "mvn_test",
                "mvn_build",
                "mvn_compile",
                "mvn_package",
                "mvn_clean",
                "gradle_test",
                "gradle_build",
                "gradle_check",
                "spotbugs_check",
                "checkstyle_check",
            }
        ),
        ("maven", "mvn", "gradle", "spring"),
    ),
    "dotnet": (
        frozenset(
            {
                "dotnet_test",
                "dotnet_build",
                "dotnet_restore",
                "dotnet_clean",
                "dotnet_fmt",
                "dotnet_format",
                "dotnet_tool_install",
                "dotnet_outdated",
                "dotnet_ef_migrations",
            }
        ),
        ("dotnet", "csharp", "c#", "asp.net", ".net"),
    ),
}


# Tool yang boleh dipakai di Plan Mode (observasi). Tool mutasi (write_file,
# apply_patch, git_commit, repo_issue, repo_pr, dsb) DIBLOKIR.
READONLY_ALLOWED_TOOLS = frozenset({
    "terminal",  # dirinya sendiri yang membatasi perintah (is_readonly_command)
    "read_file", "grep", "find_files",
    "web_fetch", "web_search", "http_request", "sys_info",
    "git_status", "git_diff", "git_log",
    "code_map", "code_map_multi", "dep_graph", "semantic_search",
    "repo_issues",
    "todo_list", "mem_search", "memory_get", "memory_search",
    "poll_bg", "read_document", "read_image", "data_query",
})


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON-schema ringkas
    fn: Callable[..., Any]


class ToolRegistry:
    def __init__(
        self, allowlist: list[str] | None = None, base_dir: str | Path | None = None
    ):
        self._tools: dict[str, ToolSpec] = {}
        self.allowlist = set(allowlist or [])
        self.tool_count: dict[str, int] = {}
        # Plan Mode: hanya tool observasi (READONLY_ALLOWED_TOOLS) yang boleh jalan.
        self.readonly: bool = False
        # Project root — tool (read/write/terminal) berjalan DI SINI, bukan di
        # folder tempat user menjalankan `dhybrid`. Dipakai per eksekusi tool
        # (chdir scoped, dikembalikan setelah selesai) supaya tidak mengubah
        # working directory global & merusak proses lain/test.
        self.base_dir = Path(base_dir).resolve() if base_dir else None

    def register(
        self, name: str, description: str, parameters: dict, fn: Callable[..., Any]
    ) -> None:
        self._tools[name] = ToolSpec(name, description, parameters, fn)

    def specs(self) -> list[dict]:
        """Tool definitions ringkas untuk system prompt (hemat token)."""
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
            if t.name in self.allowlist or not self.allowlist
        ]

    def _render_specs(self, names: list[str]) -> str:
        """Render tool definitions untuk subset nama tool tertentu."""
        lines = ["TOOLS TERSEDIA (format panggilan di akhir pesan):"]
        for name in names:
            t = self._tools.get(name)
            if t is None:
                continue
            params = ", ".join(
                f"{k}={v.get('type', '?')}" for k, v in t.parameters.items()
            )
            lines.append(f"- {t.name}({params}) — {t.description}")
        return "\n".join(lines)

    def spec_text(self) -> str:
        """Rendering tool definitions jadi teks prompt yang ringkas."""
        return self._render_specs([s["name"] for s in self.specs()])

    def spec_text_for(self, prompt: str) -> str:
        """JIT Tool Loading — hanya tool yang relevan dengan intent prompt.

        Selalu menyertakan CORE tools; kelompok lain (git, testing, toolchain
        bahasa, dsb.) dipilih via keyword pada prompt. Menghemat token besar
        dibanding meng-inject seluruh ~100 tool di setiap langkah.
        """
        low = (prompt or "").lower()
        chosen: set[str] = set(_CORE_TOOLS)
        for tools, keywords in _TOOL_GROUPS.values():
            if any(k in low for k in keywords):
                chosen.update(tools)
        if self.allowlist:
            chosen = {t for t in chosen if t in self.allowlist}
        names = [name for name in self._tools if name in chosen]
        return self._render_specs(names) or self.spec_text()

    def execute(self, name: str, arguments: dict) -> str:
        if name not in self._tools:
            return f"ERROR: tool '{name}' tidak dikenal"
        if self.allowlist and name not in self.allowlist:
            return f"ERROR: tool '{name}' tidak diizinkan (allowlist)"
        if self.readonly and name not in READONLY_ALLOWED_TOOLS:
            return (
                f"ERROR: Plan Mode — tool '{name}' bersifat mutasi/eksekusi, diblokir. "
                "Observasi saja (read_file, grep, terminal read-only, git status/log/diff). "
                "Ganti ke Build Mode (Tab) untuk menggunakan tool ini."
            )
        self.tool_count[name] = self.tool_count.get(name, 0) + 1
        try:
            cleaned = validate_args(self._tools[name].parameters, arguments)
        except ValueError as e:
            return f"ERROR argumen {name}: {e}"
        try:
            if self.base_dir and self.base_dir != Path.cwd().resolve():
                # jalankan tool di project root, lalu kembalikan cwd semula
                with chdir(self.base_dir):
                    out = self._tools[name].fn(**cleaned)
            else:
                out = self._tools[name].fn(**cleaned)
            return str(out)
        except TypeError as e:
            return f"ERROR argumen {name}: {e}"
        except Exception as e:  # noqa: BLE001
            return f"ERROR {name}: {type(e).__name__}: {e}"

    def reset_counts(self) -> None:
        """Kosongkan penghitung pemakaian tool — dipanggil tiap awal run agent
        supaya auto-skill hanya melihat tool run INI, bukan akumulasi sesi."""
        self.tool_count = {}
