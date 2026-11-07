import importlib
import inspect
import os
from glob import glob
from pathlib import Path
from typing import List

from backend.mythic_agent.mythic_agent import MythicAgent, ScriptCommand
from utils.logger import logger


class PluginAgent(MythicAgent):
    """Base class for an installed plugin's agent. Overrides the two MythicAgent methods that
    hard-code `agents/<Name>/` so a plugin resolves files relative to its own installed package
    instead, without any change to MythicAgent itself."""

    def get_files(self, folder: str) -> List[Path]:
        target_files = []
        package_root = Path(inspect.getfile(type(self))).resolve().parent
        folder_path = package_root / folder

        files = glob(os.path.join(str(folder_path), "*.py"))
        for file in files:
            path = Path(file)
            if path.name == "__init__.py":
                continue
            target_files.append(path)

        return target_files

    def get_script_classes(self) -> List[ScriptCommand]:
        script_files = self.get_script_files()
        self.scripts = []

        package_root = type(self).__module__.rsplit(".", 1)[0]

        for path in script_files:
            module_name = path.stem
            module_path = f"{package_root}.scripts.{module_name}"
            try:
                module = importlib.import_module(module_path)
            except ImportError as e:
                logger.warning(f"failed to import script module {module_name}: {e}")
                continue

            for _, member in inspect.getmembers(module, inspect.isclass):
                if issubclass(member, ScriptCommand) and member.__module__ == module.__name__:
                    self.scripts.append(member(self))

        return self.scripts
