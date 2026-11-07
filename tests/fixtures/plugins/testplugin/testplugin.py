from backend.mythic_agent.mythic_agent import AgentCommands
from plugins.base import PluginAgent

from .commands.net import Net
from .formatter import TestPluginFormatter


class TestPlugin(PluginAgent):
    def __init__(self, instance):
        super().__init__("testplugin", instance, TestPluginFormatter())

    async def get_agent_commands(self) -> AgentCommands:
        cmds = await super().get_agent_commands()

        for name in ("echo", "connect"):
            cmds.pop(name, None)
        cmds["net"] = Net(self)

        return cmds
