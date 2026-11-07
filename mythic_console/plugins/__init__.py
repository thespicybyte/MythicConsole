from .base import PluginAgent
from .installer import install, install_from_github, install_from_path, list_installed, remove
from .manifest import InvalidManifest, PluginManifest, load_manifest
from .registry import PluginRegistry, get_plugin_registry, load_installed_plugins

__all__ = [
    "PluginAgent",
    "PluginManifest",
    "InvalidManifest",
    "load_manifest",
    "PluginRegistry",
    "get_plugin_registry",
    "load_installed_plugins",
    "install",
    "install_from_path",
    "install_from_github",
    "list_installed",
    "remove",
]
