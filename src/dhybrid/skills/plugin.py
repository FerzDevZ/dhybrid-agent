"""Skill Plugin System — daftarkan skill & tool secara programatik.

Memungkinkan skill membawa tool sendiri (bukan cuma instruksi prompt), plus
deklarasi dependency & parameter templating.

```python
@dskill(
    name="pytest-expert",
    version="1.0.0",
    tools=["run_tests", "read_file"],
    dependencies=["postgres-testing"],
)
def pytest_expert() -> SkillPlugin:
    return SkillPlugin(
        name="pytest-expert",
        version="1.0.0",
        description="Jalankan dan perbaiki test pytest.",
        prompt_prefix="Fokus pada pytest: jalankan test terkecil, perbaiki, ulangi.",
    )
```

Registry melakukan auto-discovery dari:
- project `./skills/` (berkas & subfolder `*.py`)
- user  `~/.dhybrid/skills/plugins/`
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("dhybrid.skills.plugin")


def _warn(msg: str) -> None:
    logger.warning(msg)

# Registry yang sedang dipakai `@dskill` selama `discover()` / load module.
# Default `None` → dekorator memakai `default_registry()` (global singleton).
_ACTIVE_REGISTRY: SkillPluginRegistry | None = None


@dataclass
class SkillPlugin:
    """Deklarasi skill programatik yang bisa membawa tool."""
    name: str
    version: str
    description: str
    prompt_prefix: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)


class PluginRegistryError(Exception):
    """Error saat load plugin skill."""


@dataclass
class RegisteredPlugin:
    """Plugin yang berhasil didaftarkan."""
    plugin: SkillPlugin
    module: str


class SkillPluginRegistry:
    """Registry plugin skill + auto-discovery."""

    def __init__(self, search_dirs: list[str | Path] | None = None):
        self._plugins: dict[str, RegisteredPlugin] = {}
        self._search_dirs = [Path(d) for d in (search_dirs or [])]
        self._loaded_paths: set[str] = set()

    def register(self, plugin: SkillPlugin, factory: str = "<registered>") -> None:
        if not plugin.name:
            raise PluginRegistryError("Nama plugin skill wajib diisi")
        self._plugins[plugin.name] = RegisteredPlugin(plugin=plugin, module=factory)

    def register_decorator(self, plugin: SkillPlugin) -> None:
        """Dipakai oleh @dskill_plugin."""
        self.register(plugin)

    def get(self, name: str) -> SkillPlugin | None:
        rp = self._plugins.get(name)
        return rp.plugin if rp else None

    def names(self) -> list[str]:
        return sorted(self._plugins)

    def plugins(self) -> list[SkillPlugin]:
        return [rp.plugin for rp in self._plugins.values()]

    def resolve_dependencies(self, name: str, seen: set[str]) -> list[SkillPlugin]:
        """BFS untuk mengembalikan dependency plugin tertentu (berurutan)."""
        out: list[SkillPlugin] = []
        stack = [self.get(name)]
        while stack:
            pl = stack.pop()
            if pl is None or pl.name in seen:
                continue
            seen.add(pl.name)
            out.append(pl)
            for dep in reversed(pl.dependencies):
                dep_pl = self.get(dep)
                if dep_pl is not None:
                    stack.append(dep_pl)
        return list(reversed(out))

    def discover(self, dirs: list[str | Path] | None = None) -> int:
        """Auto-discovery plugin dari berkas `*.pyplugin.py` / `*.py`.

        Plugin yang didekorasi `@dskill` di dalam module yang dimuat akan
        didaftarkan ke REGISTRY INI (bukan registry global) selama load.

        Satu file yang gagal dimuat TIDAK menggagalkan yang lain — beri warning
        (log) dan lanjut ke file berikutnya; startup tetap berjalan.
        """
        global _ACTIVE_REGISTRY
        dirs = dirs or self._search_dirs
        count = 0
        prev_active = _ACTIVE_REGISTRY
        _ACTIVE_REGISTRY = self
        try:
            for base in dirs:
                d = Path(base)
                if not d.exists():
                    continue
                for f in sorted(d.rglob("*.py")):
                    if f.name.startswith("_"):
                        continue
                    key = str(f.resolve())
                    if key in self._loaded_paths:
                        continue
                    self._loaded_paths.add(key)
                    try:
                        spec = importlib.util.spec_from_file_location(f"dhybrid_skill_plugin_{f.stem}", f)
                        if spec is None or spec.loader is None:
                            continue
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        # setelah module dimuat, patch sys.modules untuk deps
                        sys.modules[mod.__name__] = mod
                    except Exception as e:  # noqa: BLE001 — 1 file gagal ≠ mati semua
                        self._loaded_paths.discard(key)
                        _warn(f"skip plugin {f}: {e}")
                        continue
                    count += 1
        finally:
            _ACTIVE_REGISTRY = prev_active
        return count

    def collect(self) -> list[SkillPlugin]:
        """Semua plugin (termasuk dependency yang ter-resolve)."""
        all_pls: list[SkillPlugin] = []
        seen: set[str] = set()
        for name in self.names():
            for pl in self.resolve_dependencies(name, seen):
                all_pls.append(pl)  # noqa: PERF402
        return all_pls


def _resolve_search_dirs(dirs: list[str | Path] | None) -> list[Path]:
    """Search dir bawaan: ./skills + ~/.dhybrid/skills/plugins."""
    out: list[Path] = []
    if dirs is not None:
        out = [Path(d) for d in dirs]
    else:
        out = [Path("skills"), Path.home() / ".dhybrid" / "skills" / "plugins"]
    return [p.expanduser() for p in out]


def default_registry() -> SkillPluginRegistry:
    """Registry global (singleton) — dipakai dekorator @dskill & discovery."""
    if not hasattr(default_registry, "_reg"):
        default_registry._reg = SkillPluginRegistry(_resolve_search_dirs(None))  # type: ignore[attr-defined]
    return default_registry._reg  # type: ignore[attr-defined]


def discover_plugins(dirs: list[str | Path] | None = None) -> int:
    """Auto-discovery ke registry global. Return jumlah module yang dimuat."""
    return default_registry().discover(dirs)


def dskill(
    name: str | None = None,
    version: str | None = None,
    description: str | None = None,
    prompt_prefix: str | None = None,
    tools: list[str] | None = None,
    dependencies: list[str] | None = None,
    parameters: dict | None = None,
) -> Callable[[Callable[[], SkillPlugin]], SkillPlugin]:
    """Dekorator untuk mendaftarkan skill plugin programatik.

    Fungsi yang didekorasi harus MENGEMBALIKAN `SkillPlugin`. Argumen
    dekorator menjadi nilai default; field di instance hasil overriding.
    """

    def _decorate(fn: Callable[[], SkillPlugin]) -> SkillPlugin:
        plugin = fn()
        if name is not None:
            plugin.name = name
        if version is not None:
            plugin.version = version
        if description is not None:
            plugin.description = description
        if prompt_prefix is not None:
            plugin.prompt_prefix = prompt_prefix
        if tools is not None:
            plugin.tools = tools
        if dependencies is not None:
            plugin.dependencies = dependencies
        if parameters is not None:
            plugin.parameters = parameters
        target = _ACTIVE_REGISTRY or default_registry()
        target.register(plugin, factory=f"{fn.__module__}.{fn.__qualname__}")
        return plugin

    return _decorate