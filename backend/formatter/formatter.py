import base64
import json
from abc import ABC, abstractmethod
from typing import Optional, List

from rich.console import Console, RenderableType
from rich.pretty import Pretty
from rich.table import Column, Table
from rich.text import Text

from ..task.task import Task, TaskNotCompleted


class Formatter(ABC):
    def __init__(self):
        self.console = Console()

    @abstractmethod
    async def format_output(self, task: Task) -> Optional["RenderableType"]:
        """
        Wrapper around all custom formatters for the agent

        :param task: Task object to have output formatted
        :rtype: Any rich renderable value
        """
        pass

    def set_console(self, console: Console):
        """
        Update the console object used for printing rich objects

        :param console:
        """
        self.console = console

    def print_output(self, output: "RenderableType"):
        """
        Print output of a task

        :param output: Any rich renderable type
        """
        self.console.print(output)

    @staticmethod
    def build_table(*rows: List[Optional["RenderableType"]], headers: List[Column | str] = None,
                    title: str = None) -> Table:
        """
        Initialize a rich.Table object to display command output.

        :param rows: List of renderable objects that will make up a row
        :param headers: List of column headers. Leave None if no headers are desired
        :param title: Title of table
        :return: rich Table object
        """
        show_header = True if headers else False
        headers = headers or []
        columns = []
        for column in headers:
            if isinstance(column, str):
                column = Column(column, overflow="fold")
            columns.append(column)

        table = Table(*columns, title=title, show_header=show_header)
        for row in rows:
            table.add_row(*row)

        return table

    @staticmethod
    async def format_plaintext(task: Task, encoding: str = 'utf8') -> Text:
        """
        Return the decoded UserOutput from a task

        :param task: task to get output from
        :param encoding: encoding type
        :return: decoded output value from UserOutput
        """
        if not task.completed:
            raise Exception("TaskNotCompleted")

        output = ""
        async for response in task.get_responses():
            encoded_b64 = response.response_text
            encoded = base64.b64decode(encoded_b64)
            output += encoded.decode(encoding=encoding)

        return Text(output)

    async def format_pretty(self, task: Task, encoding: str = 'utf8', *args, **kwargs) -> Pretty:
        """
        Return the decoded UserOutput from a task

        :param task: task to get output from
        :param encoding: encoding type
        :return: decoded output value from UserOutput
        """
        if not task.completed:
            raise TaskNotCompleted

        output = await self.get_raw_output(task, encoding)

        output_json = {}
        if isinstance(output, dict):
            output_json = output
        if isinstance(output, str):
            output_json = json.loads(output)

        return Pretty(output_json, *args, **kwargs)

    @classmethod
    async def get_raw_output(cls, task: Task, encoding: str = "utf8") -> str:
        """gets all the chunks and combines the output returning a string"""
        raw = ""
        async for chunk in task.get_responses():
            encoded_b64 = chunk.response_text
            encoded = base64.b64decode(encoded_b64)
            raw += encoded.decode(encoding=encoding)

        return raw


class DefaultFormatter(Formatter):
    async def format_output(self, task: Task) -> Optional["RenderableType"]:
        return ""
