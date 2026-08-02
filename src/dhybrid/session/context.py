"""SessionContext — wiring hub: config, router, tools, hooks, store, skills."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.router import HybridRouter
from dhybrid.config import Config, ModelConfig
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.cache import PromptCache
from dhybrid.efficiency.context import ContextManager
from dhybrid.efficiency.lazy import build_system_prompt
from dhybrid.llm.providers import make_client
from dhybrid.llm.registry import ModelRegistry
from dhybrid.session.memory import MemoryStore
from dhybrid.session.store import SessionStore
from dhybrid.skills.loader import list_skills
from dhybrid.tools import build_tools
from dhybrid.tools.registry import ToolRegistry

BASE_PROMPT = (
    "Kamu adalah dhybrid-agent, coding agent CLI yang powerful dan super hemat token. "
    "Bekerjalah langsung di workspace pengguna. Periksa dulu (read_file range kecil, grep) "
    "sebelum mengedit. Selalu verifikasi dengan menjalankan test terkecil.\n\n"
    "PANGGILAN TOOL: gunakan tool-calling native bila tersedia. Bila tidak tersedia, "
    "bungkus JSON dalam blok kode:\n"
    "```tool\n{\"name\": \"nama_tool\", \"arguments\": {...}}\n```"
)


class SessionContext:
    def __init__(
        self,
        cfg: Config,
        store: SessionStore,
        cwd: str = ".",
        sid: str | None = None,
        yes_mode: bool = False,
    ):
        self.cfg = cfg
        self.store = store
        self.cwd = cwd
        self.workspace = cfg.workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.sid = sid or store.new_session()
        self.budget = TokenBudget(soft=cfg.budget.get("soft", 60000), hard=cfg.budget.get("hard", 120000))
        self.ctx = ContextManager(keep_recent=cfg.context.get("keep_recent", 8))
        self.cache = PromptCache(db_path=self.workspace / "cache.sqlite")
        self.registry = ModelRegistry(cfg)
        self.model_cfg = cfg.model  # model utama (big)
        self.small_model_name = cfg.small_model
        # memori per-proyek: hash cwd → folder terpisah (sesi tetap global)
        proj_hash = hashlib.sha256(Path(cwd).resolve().as_posix().encode()).hexdigest()[:12]
        self.memory = MemoryStore(self.workspace / "projects" / proj_hash / "memory.sqlite")
        self._cost_map: dict[str, ModelConfig] = self._build_cost_map()

        # tools + subagent factory
        self.tools: ToolRegistry = build_tools(
            cfg,
            client_factory=self._fresh_client,
            memory_store=self.memory,
        )

        self.router: HybridRouter | None = self._build_router()
        self.skills = list_skills(Path(cwd) / cfg.skills.get("dir", "skills"))
        self.system_prompt = (
            build_system_prompt(BASE_PROMPT, workspace_hint=cwd)
            + "\n\n"
            + self.tools.spec_text()
        )
        self.hooks = Hooks()
        # hooks default: catat usage ke SQLite (dipanggil loop tiap step)
        self.hooks.on_step = (
            lambda _step, model, usage, _budget: self.record_usage(model, usage)
            if usage is not None
            else None
        )
        self.yes_mode = yes_mode
        self.steps = 0
        self.last_cost = 0.0

    # ---------- build ----------

    def _build_cost_map(self) -> dict[str, ModelConfig]:
        m: dict[str, ModelConfig] = {}
        for preset in self.cfg.presets.values():
            mc = ModelConfig(**preset)
            m[mc.model] = mc
        m[self.model_cfg.model] = self.model_cfg
        return m

    def _build_router(self) -> HybridRouter | None:
        big = make_client(self.model_cfg)
        if self.small_model_name:
            small_cfg = self.registry.resolve(self.small_model_name)
            small = make_client(small_cfg)
            self._cost_map[small_cfg.model] = small_cfg
            return HybridRouter(big, small, cache=self.cache)
        return None

    def _fresh_client(self):
        """Client baru (untuk subagent) — model utama."""
        return make_client(self.model_cfg)

    def cost_for(self, model: str, prompt: int, completion: int) -> float:
        return self._cost_map.get(model, self.model_cfg).cost(prompt, completion)

    # ---------- model switching ----------

    def resolve_model_input(self, name: str) -> ModelConfig:
        """Terima: nama preset → 'provider:model' → model manual (route/provider aktif)."""
        if name in self.registry.presets:
            return self.registry.resolve(name)
        if ":" in name:
            return self.registry.resolve(name)
        # manual: model apa pun di route/provider aktif (mis. di route zen: gpt-5.6-luna)
        return ModelConfig(
            provider=self.model_cfg.provider,
            model=name,
            base_url=self.model_cfg.base_url,
            api_key_env=self.model_cfg.api_key_env,
            max_tokens=self.model_cfg.max_tokens,
            temperature=self.model_cfg.temperature,
        )

    def set_model(self, preset: str) -> str:
        new_cfg = self.resolve_model_input(preset)
        self.model_cfg = new_cfg
        self._cost_map[new_cfg.model] = new_cfg
        self.router = self._build_router()
        from dhybrid.session.userconfig import save_model_choice
        save_model_choice(new_cfg)  # persisten — bertahan setelah restart
        return f"model utama -> {preset} ({new_cfg.model} via {new_cfg.provider}) — tersimpan permanen"

    def set_small_model(self, name: str | None) -> str:
        """Atur model kecil router. '-' / 'none' / 'off' / kosong = nonaktifkan."""
        if name is None or name.strip().lower() in ("-", "none", "off", "false"):
            self.small_model_name = None
            self.router = self._build_router()
            return "model kecil: nonaktif (semua tugas ke model utama)"
        if name in self.registry.presets or ":" in name:
            cfg = self.registry.resolve(name)
        else:
            cfg = ModelConfig(
                provider=self.model_cfg.provider,
                model=name,
                base_url=self.model_cfg.base_url,
                api_key_env=self.model_cfg.api_key_env,
                max_tokens=self.model_cfg.max_tokens,
                temperature=self.model_cfg.temperature,
            )
        self.small_model_name = name
        self._cost_map[cfg.model] = cfg
        self.router = self._build_router()
        from dhybrid.session.userconfig import save_small_model
        save_small_model(name)  # persisten
        return f"model kecil -> {name} ({cfg.model} via {cfg.provider})"

    def current_model_label(self) -> str:
        return f"{self.model_cfg.model} ({self.model_cfg.provider})"

    # ---------- usage recording ----------

    def record_usage(self, model: str, usage) -> None:
        if usage is None:
            return
        cost = self.cost_for(model, usage.prompt_tokens, usage.completion_tokens)
        self.last_cost += cost
        self.store.record_usage(
            self.sid,
            model,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.cached_tokens,
            cost,
        )
