from rich.text import Text

from backend import Formatter, Task, renders


class TestPluginFormatter(Formatter):
    @renders("echo")
    async def echo(self, task: Task) -> Text:
        raw = await self.get_raw_output(task)
        return Text(raw.upper())
