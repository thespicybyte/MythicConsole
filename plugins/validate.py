import importlib
import inspect
import sys
from pathlib import Path
from typing import List, Tuple

from backend.mythic_agent.mythic_agent import AgentCommand, ScriptCommand
from .loader import PluginLoadError, load_plugin
from .manifest import InvalidManifest, load_manifest


def _ensure_on_path(parent: Path) -> None:
    parent_str = str(parent)
    if parent_str not in sys.path:
        sys.path.append(parent_str)


def _defines_subclass(module, base_type: type) -> bool:
    for _, member in inspect.getmembers(module, inspect.isclass):
        if issubclass(member, base_type) and member.__module__ == module.__name__:
            return True
    return False


def validate_plugin(path: str | Path) -> Tuple[List[str], List[str]]:
    """Validate a plugin directory. Returns (errors, advisories); errors non-empty means invalid."""
    path = Path(path)
    errors: List[str] = []
    advisories: List[str] = []

    try:
        manifest = load_manifest(path)
    except InvalidManifest as e:
        errors.append(str(e))
        return errors, advisories

    if path.name != manifest.name:
        errors.append(
            f"plugin directory '{path.name}' does not match manifest name '{manifest.name}'")

    try:
        load_plugin(path)
    except PluginLoadError as e:
        errors.append(str(e))

    _ensure_on_path(path.parent)

    for folder, base_type, type_label in (("scripts", ScriptCommand, "ScriptCommand"),
                                          ("commands", AgentCommand, "AgentCommand")):
        folder_path = path / folder
        if not folder_path.is_dir():
            continue

        for file in sorted(folder_path.glob("*.py")):
            if file.name == "__init__.py":
                continue

            module_name = f"{manifest.name}.{folder}.{file.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                errors.append(f"{folder}/{file.name}: failed to import: {e}")
                continue

            if not _defines_subclass(module, base_type):
                advisories.append(f"{folder}/{file.name}: defines no {type_label} subclass")

    return errors, advisories
