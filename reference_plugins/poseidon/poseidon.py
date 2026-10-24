from backend.mythic_instance.mythic_instance import MythicInstance
from backend.mythic_agent.mythic_agent import AgentCommands, remove_background_option
from plugins.base import PluginAgent
from screens.prompts import YesNoPrompt

from .formatter import PoseidonFormatter
from .commands.directory import Directory
from .commands.file import File
from .commands.process import Process
from .commands.environment import Environment
from .commands.job import Job
from .commands.command import Command
from .commands.c2 import C2


class Poseidon(PluginAgent):
    def __init__(self, instance: MythicInstance):
        name = "poseidon"
        formatter = PoseidonFormatter()
        super().__init__(name, instance, formatter)

    async def get_agent_commands(self) -> AgentCommands:
        cmds = await super().get_agent_commands()

        for name in ("ls", "cd", "mkdir", "pwd"):
            cmds.pop(name, None)
        cmds["directory"] = Directory(self)

        for name in ("cp", "cat", "download", "head", "tail", "mv", "rm", "upload"):
            cmds.pop(name, None)
        cmds["file"] = File(self)

        for name in ("ps", "kill", "run"):
            cmds.pop(name, None)
        cmds["process"] = Process(self)

        for name in ("getenv", "setenv", "unsetenv"):
            cmds.pop(name, None)
        cmds["environment"] = Environment(self)

        for name in ("jobs", "jobkill"):
            cmds.pop(name, None)
        cmds["job"] = Job(self)

        for name in ("shell", "shell_config"):
            cmds.pop(name, None)
        cmds["command"] = Command(self)

        cmds.pop("update_c2", None)
        cmds["c2"] = C2(self)

        if "exit" in cmds:
            exit_command = cmds["exit"]
            remove_background_option(exit_command.command_parser)
            exit_command.force_background = True
            exit_command.verify_prompt = YesNoPrompt(question="Exit/kill the current session?")

        return cmds
