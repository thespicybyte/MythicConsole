import json
from pathlib import Path

import pytest

from backend.mythic_agent.mythic_agent import MythicAgent
from plugins.installer import install_from_path
from plugins.loader import PluginLoadError, load_plugin

TESTPLUGIN_DIR = Path(__file__).parent / "fixtures" / "plugins" / "testplugin"


def test_load_plugin_discovers_synthetic_test_plugin(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    loaded = load_plugin(tmp_path / "testplugin")

    assert loaded.manifest.name == "testplugin"
    assert loaded.manifest.payload_type == "testplugin"
    assert issubclass(loaded.agent_class, MythicAgent)
    assert loaded.agent_class.__name__ == "TestPlugin"


def test_load_plugin_rejects_reserved_name(tmp_path):
    plugin_dir = tmp_path / "backend"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "name": "backend",
        "payload_type": "backend",
        "entrypoint": "backend:Backend",
        "version": "1.0.0",
    }))

    with pytest.raises(PluginLoadError):
        load_plugin(plugin_dir)


def test_load_plugin_missing_entrypoint_class(tmp_path):
    plugin_dir = tmp_path / "broken"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "broken.py").write_text("")
    (plugin_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "name": "broken",
        "payload_type": "broken",
        "entrypoint": "broken:DoesNotExist",
        "version": "1.0.0",
    }))

    with pytest.raises(PluginLoadError):
        load_plugin(plugin_dir)


def test_load_plugin_entrypoint_not_a_mythic_agent(tmp_path):
    plugin_dir = tmp_path / "notanagent"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "notanagent.py").write_text("class NotAnAgent:\n    pass\n")
    (plugin_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "name": "notanagent",
        "payload_type": "notanagent",
        "entrypoint": "notanagent:NotAnAgent",
        "version": "1.0.0",
    }))

    with pytest.raises(PluginLoadError):
        load_plugin(plugin_dir)


def test_load_plugin_import_error_is_wrapped(tmp_path):
    plugin_dir = tmp_path / "importfails"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "importfails.py").write_text("import this_module_does_not_exist\n")
    (plugin_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "name": "importfails",
        "payload_type": "importfails",
        "entrypoint": "importfails:Whatever",
        "version": "1.0.0",
    }))

    with pytest.raises(PluginLoadError):
        load_plugin(plugin_dir)
