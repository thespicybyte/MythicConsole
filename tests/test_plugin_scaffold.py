from pathlib import Path

import pytest

from plugins import cli
from plugins.installer import install_from_path
from plugins.loader import load_plugin
from plugins.manifest import load_manifest
from plugins.scaffold import ScaffoldError, scaffold


@pytest.fixture(autouse=True)
def plugins_dir_env(tmp_path, monkeypatch):
    """cli.run() resolves the plugins dir via Environment().plugins_directory() even for
    actions that ignore it (new/validate); point it at tmp_path so no test touches the real
    config directory."""
    monkeypatch.setenv("PLUGIN_DIRECTORY", str(tmp_path / "unused_plugins_dir"))


def test_scaffold_creates_full_tree(tmp_path):
    target = scaffold("myagent", "myagent", parent=tmp_path)

    assert target == tmp_path / "myagent"
    for relative in ("manifest.json", "__init__.py", "myagent.py", "formatter.py", "README.md",
                     "commands/__init__.py", "commands/example.py",
                     "scripts/__init__.py", "scripts/example.py"):
        assert (target / relative).is_file(), relative


def test_scaffold_manifest_passes_load_manifest_and_matches_inputs(tmp_path):
    target = scaffold("myagent", "mypayload", author="me", description="desc", parent=tmp_path)

    manifest = load_manifest(target)

    assert manifest.name == "myagent"
    assert manifest.payload_type == "mypayload"
    assert manifest.entrypoint == "myagent:Myagent"
    assert manifest.author == "me"
    assert manifest.description == "desc"


def test_scaffolded_plugin_installs_and_loads_with_no_edits(tmp_path):
    src_parent = tmp_path / "src"
    src_parent.mkdir()
    plugins_dir = tmp_path / "plugins"

    target = scaffold("freshagent", "freshagent", parent=src_parent)
    manifest = install_from_path(target, plugins_dir)

    assert manifest.name == "freshagent"

    loaded = load_plugin(plugins_dir / "freshagent")

    assert loaded.agent_class.__name__ == "Freshagent"


def test_scaffold_rejects_invalid_name(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold("not-an-identifier", "payload", parent=tmp_path)


def test_scaffold_rejects_reserved_name(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold("backend", "payload", parent=tmp_path)


def test_scaffold_rejects_existing_target(tmp_path):
    (tmp_path / "taken").mkdir()

    with pytest.raises(ScaffoldError):
        scaffold("taken", "payload", parent=tmp_path)


def test_cli_plugin_new_invalid_name_nonzero_exit(tmp_path, capsys):
    exit_code = cli.run(["plugin", "new", "not-an-identifier", "payload", "--dir", str(tmp_path)])

    assert exit_code != 0


def test_cli_plugin_new_existing_target_nonzero_exit(tmp_path):
    (tmp_path / "taken").mkdir()

    exit_code = cli.run(["plugin", "new", "taken", "payload", "--dir", str(tmp_path)])

    assert exit_code != 0


def test_cli_plugin_new_success_zero_exit(tmp_path):
    exit_code = cli.run(["plugin", "new", "cliagent", "cliagent", "--dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "cliagent" / "manifest.json").is_file()


def test_scaffold_then_validate_round_trip_exits_zero(tmp_path):
    exit_code = cli.run(["plugin", "new", "roundtrip", "roundtrip", "--dir", str(tmp_path)])
    assert exit_code == 0

    exit_code = cli.run(["plugin", "validate", str(tmp_path / "roundtrip")])

    assert exit_code == 0
