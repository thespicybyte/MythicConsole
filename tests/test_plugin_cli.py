from pathlib import Path

import pytest

from plugins import cli
from plugins.installer import install_from_path

TESTPLUGIN_DIR = Path(__file__).parent / "fixtures" / "plugins" / "testplugin"


@pytest.fixture(autouse=True)
def plugins_dir_env(tmp_path, monkeypatch):
    """cli.run() resolves the plugins dir via Environment().plugins_directory(); point it at tmp_path."""
    monkeypatch.setenv("PLUGIN_DIRECTORY", str(tmp_path))
    return tmp_path


def test_install_local_path_returns_zero(tmp_path, capsys):
    exit_code = cli.run(["install", str(TESTPLUGIN_DIR)])

    assert exit_code == 0
    assert (tmp_path / "testplugin" / "manifest.json").is_file()
    out = capsys.readouterr().out
    assert "testplugin" in out


def test_install_duplicate_returns_nonzero(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    exit_code = cli.run(["install", str(TESTPLUGIN_DIR)])

    assert exit_code != 0


def test_plugin_list_empty(capsys):
    exit_code = cli.run(["plugin", "list"])

    assert exit_code == 0
    assert "no plugins installed" in capsys.readouterr().out


def test_plugin_list_shows_installed(tmp_path, capsys):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    exit_code = cli.run(["plugin", "list"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "testplugin" in out


def test_plugin_remove(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    exit_code = cli.run(["plugin", "remove", "testplugin"])

    assert exit_code == 0
    assert not (tmp_path / "testplugin").exists()


def test_plugin_remove_unknown_returns_nonzero():
    exit_code = cli.run(["plugin", "remove", "does-not-exist"])

    assert exit_code != 0


def test_no_args_returns_nonzero():
    exit_code = cli.run([])

    assert exit_code != 0


def test_bad_subcommand_returns_nonzero():
    exit_code = cli.run(["bogus"])

    assert exit_code != 0
