import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from .loader import RESERVED_NAMES
from .manifest import PluginManifest, load_manifest


class PluginInstallError(Exception):
    pass


def _looks_like_url(source: str) -> bool:
    return (source.startswith("git@")
            or source.startswith("http://")
            or source.startswith("https://")
            or "github.com" in source)


def _validate_destination(name: str, plugins_dir: Path) -> Path:
    if name in RESERVED_NAMES:
        raise PluginInstallError(f"'{name}' is a reserved name and cannot be used for a plugin")

    destination = plugins_dir / name
    if destination.exists():
        raise PluginInstallError(f"a plugin named '{name}' is already installed at {destination}")

    return destination


def install_from_path(src: str | Path, plugins_dir: str | Path) -> PluginManifest:
    """Install a plugin from a local folder: validate its manifest, then copy it into place."""
    src = Path(src)
    plugins_dir = Path(plugins_dir)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(src)
    destination = _validate_destination(manifest.name, plugins_dir)

    shutil.copytree(src, destination, ignore=shutil.ignore_patterns(".git"))
    return manifest


def install_from_github(url: str, plugins_dir: str | Path, branch: Optional[str] = None,
                        subdir: Optional[str] = None) -> PluginManifest:
    """Install a plugin by cloning a GitHub repo into a temp dir, then installing it like a local path."""
    plugins_dir = Path(plugins_dir)
    plugins_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "clone"
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [url, str(clone_dir)]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise PluginInstallError(f"git clone failed: {result.stderr.strip()}")

        plugin_root = clone_dir / subdir if subdir else clone_dir
        return install_from_path(plugin_root, plugins_dir)


def install(source: str, plugins_dir: str | Path, branch: Optional[str] = None,
           subdir: Optional[str] = None) -> PluginManifest:
    """Dispatch to install_from_github or install_from_path based on what `source` looks like."""
    if _looks_like_url(source):
        return install_from_github(source, plugins_dir, branch=branch, subdir=subdir)
    return install_from_path(source, plugins_dir)


def list_installed(plugins_dir: str | Path) -> List[PluginManifest]:
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.is_dir():
        return []

    manifests = []
    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or not (entry / "manifest.json").is_file():
            continue
        try:
            manifests.append(load_manifest(entry))
        except Exception:
            continue

    return manifests


def remove(name: str, plugins_dir: str | Path) -> None:
    plugins_dir = Path(plugins_dir)
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise PluginInstallError(f"invalid plugin name: {name!r}")

    target = plugins_dir / name
    if target.resolve().parent != plugins_dir.resolve():
        raise PluginInstallError(f"invalid plugin name: {name!r}")

    if not target.is_dir():
        raise PluginInstallError(f"no plugin named '{name}' is installed")

    shutil.rmtree(target)
