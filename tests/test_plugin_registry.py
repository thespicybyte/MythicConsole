import json
from pathlib import Path

from plugins import registry
from plugins.installer import install_from_path
from plugins.registry import PluginRegistry, get_plugin_registry

TESTPLUGIN_DIR = Path(__file__).parent / "fixtures" / "plugins" / "testplugin"


def _write_manifest(plugin_dir: Path, **overrides):
    plugin_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "name": plugin_dir.name,
        "payload_type": plugin_dir.name,
        "entrypoint": f"{plugin_dir.name}:Whatever",
        "version": "1.0.0",
    }
    data.update(overrides)
    (plugin_dir / "manifest.json").write_text(json.dumps(data))


def test_discover_finds_the_synthetic_test_plugin(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    reg = PluginRegistry()
    reg.discover(tmp_path)

    agent_class = reg.agent_class_for("testplugin")
    assert agent_class is not None
    assert agent_class.__name__ == "TestPlugin"


def test_agent_class_for_unknown_payload_type_is_none(tmp_path):
    reg = PluginRegistry()
    reg.discover(tmp_path)

    assert reg.agent_class_for("does-not-exist") is None


def test_discover_nonexistent_dir_is_empty(tmp_path):
    reg = PluginRegistry()
    reg.discover(tmp_path / "does-not-exist")

    assert reg.list_loaded() == []


def test_discover_skips_a_broken_plugin_without_crashing(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)
    _write_manifest(tmp_path / "broken", entrypoint="nope")  # invalid entrypoint shape

    reg = PluginRegistry()
    reg.discover(tmp_path)

    assert reg.agent_class_for("testplugin") is not None
    assert len(reg.list_loaded()) == 1


def test_discover_duplicate_payload_type_first_wins(tmp_path):
    agent_class_source = (
        "from backend.mythic_agent.mythic_agent import MythicAgent\n"
        "from backend.formatter.formatter import DefaultFormatter\n"
        "class Whatever(MythicAgent):\n"
        "    def __init__(self, instance):\n"
        "        super().__init__({name!r}, instance, DefaultFormatter())\n"
    )

    _write_manifest(tmp_path / "first", payload_type="dupe", entrypoint="first:Whatever")
    (tmp_path / "first" / "__init__.py").write_text("")
    (tmp_path / "first" / "first.py").write_text(agent_class_source.format(name="first"))

    _write_manifest(tmp_path / "second", payload_type="dupe", entrypoint="second:Whatever")
    (tmp_path / "second" / "__init__.py").write_text("")
    (tmp_path / "second" / "second.py").write_text(agent_class_source.format(name="second"))

    reg = PluginRegistry()
    reg.discover(tmp_path)

    loaded = reg.list_loaded()
    assert len(loaded) == 1
    assert loaded[0].manifest.name == "first"


def test_get_plugin_registry_uses_configured_plugins_dir(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)
    registry.reset()
    registry.set_plugins_dir(str(tmp_path))

    try:
        reg = get_plugin_registry()
        assert reg.agent_class_for("testplugin") is not None
    finally:
        registry.reset()


def test_registry_reload_picks_up_newly_installed_plugin(tmp_path):
    registry.reset()
    registry.set_plugins_dir(str(tmp_path))

    try:
        reg = get_plugin_registry()
        assert reg.agent_class_for("testplugin") is None

        install_from_path(TESTPLUGIN_DIR, tmp_path)
        reg.reload()

        assert reg.agent_class_for("testplugin") is not None
    finally:
        registry.reset()
