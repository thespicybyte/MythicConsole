import shutil
import types
from pathlib import Path

import pytest

from plugins import installer
from plugins.installer import (
    PluginInstallError,
    install,
    install_from_github,
    install_from_path,
    list_installed,
    remove,
)

TESTPLUGIN_DIR = Path(__file__).parent / "fixtures" / "plugins" / "testplugin"


def test_install_from_path_copies_plugin_into_plugins_dir(tmp_path):
    manifest = install_from_path(TESTPLUGIN_DIR, tmp_path)

    assert manifest.name == "testplugin"
    assert (tmp_path / "testplugin" / "manifest.json").is_file()
    assert (tmp_path / "testplugin" / "testplugin.py").is_file()


def test_install_from_path_rejects_duplicate_name(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    with pytest.raises(PluginInstallError):
        install_from_path(TESTPLUGIN_DIR, tmp_path)


def test_install_from_path_rejects_reserved_name(tmp_path):
    reserved_src = tmp_path / "src" / "backend"
    reserved_src.mkdir(parents=True)
    (reserved_src / "manifest.json").write_text(
        '{"schema_version": 1, "name": "backend", "payload_type": "backend", '
        '"entrypoint": "backend:Backend", "version": "1.0.0"}')

    with pytest.raises(PluginInstallError):
        install_from_path(reserved_src, tmp_path / "plugins")


def test_install_from_github_clones_and_installs(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text):
        clone_dir = Path(cmd[-1])
        shutil.copytree(TESTPLUGIN_DIR, clone_dir)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    manifest = install_from_github("https://github.com/example/testplugin", tmp_path)

    assert manifest.name == "testplugin"
    assert (tmp_path / "testplugin" / "manifest.json").is_file()


def test_install_from_github_with_subdir(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text):
        clone_dir = Path(cmd[-1])
        (clone_dir / "plugin").mkdir(parents=True)
        shutil.copytree(TESTPLUGIN_DIR, clone_dir / "plugin", dirs_exist_ok=True)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    manifest = install_from_github("https://github.com/example/repo", tmp_path, subdir="plugin")

    assert manifest.name == "testplugin"


def test_install_from_github_clone_failure_raises(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text):
        return types.SimpleNamespace(returncode=128, stdout="", stderr="fatal: repository not found")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    with pytest.raises(PluginInstallError):
        install_from_github("https://github.com/example/missing", tmp_path)


@pytest.mark.parametrize("source", [
    "https://github.com/example/testplugin",
    "git@github.com:example/testplugin.git",
])
def test_install_dispatches_to_github_for_url_like_sources(tmp_path, monkeypatch, source):
    def fake_run(cmd, capture_output, text):
        clone_dir = Path(cmd[-1])
        shutil.copytree(TESTPLUGIN_DIR, clone_dir)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    manifest = install(source, tmp_path)

    assert manifest.name == "testplugin"


def test_install_dispatches_to_local_path_otherwise(tmp_path):
    manifest = install(str(TESTPLUGIN_DIR), tmp_path)

    assert manifest.name == "testplugin"


def test_list_installed_empty_dir(tmp_path):
    assert list_installed(tmp_path) == []


def test_list_installed_nonexistent_dir(tmp_path):
    assert list_installed(tmp_path / "does-not-exist") == []


def test_list_installed_returns_manifests(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    manifests = list_installed(tmp_path)

    assert [m.name for m in manifests] == ["testplugin"]


def test_remove_deletes_plugin_dir(tmp_path):
    install_from_path(TESTPLUGIN_DIR, tmp_path)

    remove("testplugin", tmp_path)

    assert not (tmp_path / "testplugin").exists()


def test_remove_unknown_plugin_raises(tmp_path):
    with pytest.raises(PluginInstallError):
        remove("does-not-exist", tmp_path)


@pytest.mark.parametrize("bad_name", ["../escape", "a/b", ".", ".."])
def test_remove_rejects_path_traversal(tmp_path, bad_name):
    with pytest.raises(PluginInstallError):
        remove(bad_name, tmp_path)
