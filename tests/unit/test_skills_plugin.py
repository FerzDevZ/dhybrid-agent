from dhybrid.skills.plugin import (
    PluginRegistryError,
    SkillPlugin,
    SkillPluginRegistry,
    dskill,
)


def test_register_and_get():
    reg = SkillPluginRegistry()
    pl = SkillPlugin(name="a", version="1.0.0", description="plugin a")
    reg.register(pl)
    assert reg.get("a") is pl
    assert reg.names() == ["a"]


def test_register_requires_name():
    reg = SkillPluginRegistry()
    try:
        reg.register(SkillPlugin(name="", version="1.0.0", description=""))
    except PluginRegistryError:
        pass
    else:
        raise AssertionError("register harus menolak plugin tanpa nama")


def test_resolve_dependencies_bfs_order():
    # a -> b -> c, plus dep lain d (cacah dep a yang lain)
    reg = SkillPluginRegistry()
    reg.register(SkillPlugin(name="c", version="1", description="c"))
    reg.register(SkillPlugin(name="d", version="1", description="d"))
    reg.register(SkillPlugin(name="b", version="1", description="b", dependencies=["c"]))
    reg.register(SkillPlugin(name="a", version="1", description="a", dependencies=["b", "d"]))
    deps = reg.resolve_dependencies("a", set())
    names = [p.name for p in deps]
    # dependency muncul SEBELUM penggunanya (topological), root terakhir
    assert names[-1] == "a"
    assert names.index("c") < names.index("b")
    assert names.index("b") < names.index("a")
    assert names.index("d") < names.index("a")
    assert set(names) == {"a", "b", "c", "d"}


def test_resolve_dependencies_circular_safe():
    reg = SkillPluginRegistry()
    reg.register(SkillPlugin(name="x", version="1", description="x", dependencies=["y"]))
    reg.register(SkillPlugin(name="y", version="1", description="y", dependencies=["x"]))
    deps = reg.resolve_dependencies("x", set())
    names = [p.name for p in deps]
    assert set(names) == {"x", "y"}
    assert len(names) == 2  # tidak ada infinite loop


def test_collect_deduplicates_across_branches():
    reg = SkillPluginRegistry()
    reg.register(SkillPlugin(name="base", version="1", description="base"))
    reg.register(SkillPlugin(name="p1", version="1", description="p1", dependencies=["base"]))
    reg.register(SkillPlugin(name="p2", version="1", description="p2", dependencies=["base"]))
    names = [p.name for p in reg.collect()]
    assert names.count("base") == 1
    assert set(names) == {"base", "p1", "p2"}


def test_dskill_decorator_registers():
    @dskill(name="pytest-expert", version="1.0.0", tools=["run_tests"])
    def _make() -> SkillPlugin:
        return SkillPlugin(name="x", version="0.0.1", description="asli")

    # dekorator mendaftar ke registry global, bukan `reg`
    assert _make.name == "pytest-expert"
    assert _make.version == "1.0.0"
    assert _make.tools == ["run_tests"]
    # field yang tidak dioverride tetap dari return fungsi
    assert _make.description == "asli"


def test_discover_loads_plugin_modules(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    (d / "hello_plugin.py").write_text(
        "from dhybrid.skills.plugin import dskill, SkillPlugin\n"
        "@dskill(name='hello', description='selamat datang')\n"
        "def _reg():\n"
        "    return SkillPlugin(name='hello', version='1.0.0', description='x')\n"
    )
    reg = SkillPluginRegistry([d])
    count = reg.discover()
    assert count == 1
    assert reg.get("hello") is not None


def test_discover_bad_file_does_not_crash(tmp_path):
    """Satu file plugin rusak tak boleh menggagalkan startup — dilewati."""
    d = tmp_path / "skills"
    d.mkdir()
    (d / "good_plugin.py").write_text(
        "from dhybrid.skills.plugin import dskill, SkillPlugin\n"
        "@dskill(name='good', description='ok')\n"
        "def _g():\n"
        "    return SkillPlugin(name='good', version='1.0.0', description='ok')\n"
    )
    # file dengan syntax error → harus di-skip, bukan raise
    (d / "broken_plugin.py").write_text("def ini_syntax_error(:\n")
    reg = SkillPluginRegistry([d])
    count = reg.discover()  # tidak boleh raise
    assert count == 1  # hanya good yang terhitung
    assert reg.get("good") is not None
    assert reg.get("broken_plugin") is None