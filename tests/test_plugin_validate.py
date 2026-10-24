import json
from pathlib import Path

import pytest

from plugins import cli
from plugins.scaffold import scaffold
from plugins.validate import validate_plugin

TESTPLUGIN_DIR = Path(__file__).parent / "fixtures" / "plugins" / "testplugin"


@pytest.fixture(autouse=True)
def plugins_dir_env(tmp_path, monkeypatch):
    """cli.run() resolves the plugins dir via Environment().plugins_directory() even for
    actions that ignore it (new/validate); point it at tmp_path so no test touches the real
    config directory."""
    monkeypatch.setenv("PLUGIN_DIRECTORY", str(tmp_path / "unused_plugins_dir"))


def _write_manifest(plugin_dir: Path, **overrides) -> None:
    data = {
        "schema_version": 1,
        "name": plugin_dir.name,
        "payload_type": plugin_dir.name,
        "entrypoint": f"{plugin_dir.name}:{plugin_dir.name.capitalize()}",
        "version": "0.1.0",
    }
    data.update(overrides)
    (plugin_dir / "manifest.json").write_text(json.dumps(data))


def test_valid_plugin_has_no_errors():
    errors, advisories = validate_plugin(TESTPLUGIN_DIR)

    assert errors == []


def test_freshly_scaffolded_plugin_has_no_errors(tmp_path):
    target = scaffold("goodagent", "goodagent", parent=tmp_path)

    errors, advisories = validate_plugin(target)

    assert errors == []
    assert advisories


def test_bad_manifest_missing_field(tmp_path):
    plugin_dir = tmp_path / "badmanifest"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "badmanifest.py").write_text("")
    (plugin_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "name": "badmanifest",
        "payload_type": "badmanifest",
        "version": "0.1.0",
    }))

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("entrypoint" in e for e in errors)


def test_bad_schema_version(tmp_path):
    plugin_dir = tmp_path / "badschema"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "badschema.py").write_text("")
    _write_manifest(plugin_dir, schema_version=2)

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("schema_version" in e for e in errors)


def test_unresolvable_entrypoint(tmp_path):
    plugin_dir = tmp_path / "noentry"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "noentry.py").write_text("")
    _write_manifest(plugin_dir, entrypoint="noentry:DoesNotExist")

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("DoesNotExist" in e for e in errors)


def test_entrypoint_not_a_mythic_agent(tmp_path):
    plugin_dir = tmp_path / "notanagent"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "notanagent.py").write_text("class NotAnAgent:\n    pass\n")
    _write_manifest(plugin_dir, entrypoint="notanagent:NotAnAgent")

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("MythicAgent" in e for e in errors)


def test_import_error_in_scripts_module(tmp_path):
    plugin_dir = tmp_path / "brokenscript"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "brokenscript.py").write_text(
        "from plugins.base import PluginAgent\n\n"
        "class Brokenscript(PluginAgent):\n"
        "    def __init__(self, instance):\n"
        "        super().__init__('brokenscript', instance, None)\n")
    scripts_dir = plugin_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "bad.py").write_text("import this_module_does_not_exist\n")
    _write_manifest(plugin_dir, entrypoint="brokenscript:Brokenscript")

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("bad.py" in e for e in errors)


def test_import_error_in_commands_module(tmp_path):
    plugin_dir = tmp_path / "brokencommand"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "brokencommand.py").write_text(
        "from plugins.base import PluginAgent\n\n"
        "class Brokencommand(PluginAgent):\n"
        "    def __init__(self, instance):\n"
        "        super().__init__('brokencommand', instance, None)\n")
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "__init__.py").write_text("")
    (commands_dir / "bad.py").write_text("import this_module_does_not_exist\n")
    _write_manifest(plugin_dir, entrypoint="brokencommand:Brokencommand")

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("bad.py" in e for e in errors)


def test_dir_name_mismatch(tmp_path):
    plugin_dir = tmp_path / "actualdir"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "mismatched.py").write_text("")
    _write_manifest(plugin_dir, name="mismatched", entrypoint="mismatched:Mismatched")

    errors, _ = validate_plugin(plugin_dir)

    assert errors
    assert any("actualdir" in e and "mismatched" in e for e in errors)


def test_script_module_with_no_subclass_is_advisory_not_error(tmp_path):
    plugin_dir = tmp_path / "noscriptclass"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    (plugin_dir / "noscriptclass.py").write_text(
        "from plugins.base import PluginAgent\n\n"
        "class Noscriptclass(PluginAgent):\n"
        "    def __init__(self, instance):\n"
        "        super().__init__('noscriptclass', instance, None)\n")
    scripts_dir = plugin_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "empty.py").write_text("def helper():\n    return 1\n")
    _write_manifest(plugin_dir, entrypoint="noscriptclass:Noscriptclass")

    errors, advisories = validate_plugin(plugin_dir)

    assert errors == []
    assert any("empty.py" in a for a in advisories)


def test_cli_validate_good_plugin_exits_zero():
    exit_code = cli.run(["plugin", "validate", str(TESTPLUGIN_DIR)])

    assert exit_code == 0


def test_cli_validate_bad_plugin_exits_nonzero(tmp_path):
    plugin_dir = tmp_path / "badcli"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    _write_manifest(plugin_dir, entrypoint="badcli:DoesNotExist")

    exit_code = cli.run(["plugin", "validate", str(plugin_dir)])

    assert exit_code != 0
