from pathlib import Path
from typing import Dict, List, Optional, Type

from backend.mythic_agent.mythic_agent import MythicAgent
from utils.environment import Environment
from utils.logger import logger
from .loader import LoadedPlugin, load_plugin


class PluginRegistry:
    """Maps a Mythic payload type name to the installed plugin's agent class."""

    def __init__(self):
        self._plugins: Dict[str, LoadedPlugin] = {}

    def discover(self, plugins_dir: str | Path) -> None:
        self._plugins = {}
        plugins_dir = Path(plugins_dir)
        if not plugins_dir.is_dir():
            return

        for entry in sorted(plugins_dir.iterdir()):
            if not entry.is_dir() or not (entry / "manifest.json").is_file():
                continue

            try:
                loaded = load_plugin(entry)
            except Exception as e:
                logger.warning(f"skipping plugin at {entry}: {e}")
                continue

            payload_type = loaded.manifest.payload_type
            if payload_type in self._plugins:
                logger.warning(
                    f"duplicate plugin for payload type '{payload_type}' at {entry}; "
                    f"keeping {self._plugins[payload_type].path}")
                continue

            self._plugins[payload_type] = loaded
            logger.info(f"loaded plugin '{loaded.manifest.name}' for payload type '{payload_type}'")

    def agent_class_for(self, payload_type: str) -> Optional[Type[MythicAgent]]:
        loaded = self._plugins.get(payload_type)
        return loaded.agent_class if loaded else None

    def list_loaded(self) -> List[LoadedPlugin]:
        return list(self._plugins.values())

    def reload(self) -> None:
        """Re-discover from the same plugins dir this registry was built from."""
        self.discover(_resolve_plugins_dir())


_registry: Optional[PluginRegistry] = None
_plugins_dir_override: Optional[str] = None


def set_plugins_dir(path: Optional[str]) -> None:
    """Test hook: override the plugins dir used by `get_plugin_registry`/`load_installed_plugins`."""
    global _plugins_dir_override
    _plugins_dir_override = path


def _resolve_plugins_dir() -> str:
    return _plugins_dir_override or Environment().plugins_directory()


def get_plugin_registry() -> PluginRegistry:
    """Lazy singleton: discovers from the plugins dir on first access."""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
        _registry.discover(_resolve_plugins_dir())
    return _registry


def load_installed_plugins() -> PluginRegistry:
    """Explicit startup call: (re)discover and log every installed plugin."""
    global _registry
    _registry = PluginRegistry()
    _registry.discover(_resolve_plugins_dir())
    return _registry


def reset() -> None:
    """Test hook: drop the singleton registry and any plugins-dir override."""
    global _registry
    _registry = None
    set_plugins_dir(None)
