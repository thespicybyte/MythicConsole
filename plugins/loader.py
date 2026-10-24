import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Type

from backend.mythic_agent.mythic_agent import MythicAgent
from .manifest import PluginManifest, load_manifest

RESERVED_NAMES = frozenset({
    "backend", "agents", "screens", "widgets", "utils", "console", "plugins", "tests",
    "rich", "textual", "mythic", "cmd2",
})


class PluginLoadError(Exception):
    pass


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    agent_class: Type[MythicAgent]
    path: Path


def _ensure_on_path(plugins_dir: Path) -> None:
    plugins_dir_str = str(plugins_dir)
    if plugins_dir_str not in sys.path:
        sys.path.append(plugins_dir_str)


def load_plugin(plugin_dir: Path) -> LoadedPlugin:
    """Load one installed plugin folder into a `LoadedPlugin` (manifest + resolved agent class)."""
    plugin_dir = Path(plugin_dir)
    manifest = load_manifest(plugin_dir)

    if manifest.name in RESERVED_NAMES:
        raise PluginLoadError(
            f"plugin '{manifest.name}' uses a reserved package name and cannot be loaded")

    _ensure_on_path(plugin_dir.parent)

    try:
        importlib.import_module(manifest.name)
        module = importlib.import_module(f"{manifest.name}.{manifest.entrypoint_module}")
    except ImportError as e:
        raise PluginLoadError(f"plugin '{manifest.name}': failed to import entrypoint: {e}")

    agent_class = getattr(module, manifest.entrypoint_class, None)
    if agent_class is None:
        raise PluginLoadError(
            f"plugin '{manifest.name}': entrypoint class '{manifest.entrypoint_class}' "
            f"not found in '{manifest.entrypoint_module}'")

    if not (isinstance(agent_class, type) and issubclass(agent_class, MythicAgent)):
        raise PluginLoadError(
            f"plugin '{manifest.name}': entrypoint '{manifest.entrypoint}' is not a MythicAgent subclass")

    return LoadedPlugin(manifest=manifest, agent_class=agent_class, path=plugin_dir)
