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
            class_name = module_name.capitalize()
            try:
                module_path = f"{package_root}.scripts.{module_name}"
                module = importlib.import_module(module_path)

                script_class = getattr(module, class_name, None)
                if script_class is None:
                    logger.debug(f"Class {class_name} not found in {module_name}.py")
                    continue

                if not issubclass(script_class, ScriptCommand):
                    logger.debug(f"{script_class.__name__} is not an ScriptCommand")
                    continue

                script = script_class(self)
                self.scripts.append(script)

            except (ImportError, AttributeError) as e:
                logger.warning(f"Failed to load class {class_name} from {module_name}.py: {e}")

        return self.scripts
