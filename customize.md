# Extending Mythic Console

Extending Mythic Console to support your own agent is easy to do.
There are three steps to take:

1. Register your agent by creating the required file structure
    1. Create your agent class
    2. Add your agent to the agent initializer
2. Define your commands
3. Define how the output should be formatted

## Registering additional agents

Simply create the file structure depicted below:

 ```markdown
 mythic_console
├── agents
│ ├── __init__.py
│ ├── NewAgent
│ │ ├── commands
│ │ ├── scripts
│ │ ├── __init__.py
│ │ ├── formatter.py
│ │ ├── new_agent.py
 ```

Once the file structure is set up, create your agent class.
A Mythic Agent class requires just two things, it's name defined and an optional `Formatter` (described later).
If you do not have a custom formatter, the default one can be used.

```python
from backend import Formatter
from backend.mythic_agent.mythic_agent import MythicAgent
from backend.mythic_instance.mythic_instance import MythicInstance


class NewAgent(MythicAgent):
    def __init__(self, instance: MythicInstance):
        name = "new_agent"
        formatter = Formatter()
        super().__init__(name, instance, formatter)
```

After defining your agent, you can add it to the agents `__init__` file so the Console will recognize it.
Note that whatever goes into the `case` field is the name of your agent as Mythic refers to.

```python
from backend.mythic_instance.mythic_instance import MythicInstance
from agents.Poseidon.poseidon import Poseidon
from agents.NewAgent.new_agent import NewAgent


class UnknownAgent(Exception):
    def __init__(self, payload_type_name: str):
        super().__init__(payload_type_name)


def get_agent(instance: MythicInstance, payload_type_name: str) -> Poseidon:
    match payload_type_name:
        case "poseidon":
            return Poseidon(instance)
        case "new_agent":
            return NewAgent(instance)
        case _:
            raise UnknownAgent(payload_type_name)
```

## Adding Commands

Agent commands are simple to write and allow the author a lot of flexibility.
All commands must inherit the `AgentCommand` class which in
an [Abstract Base Class](https://docs.python.org/3/library/abc.html), or interface, the provides all the plumbing
necessary to subcommands, aliases, and tab completion. There are three ways to define an Agent Command: basic command,
command with sub-commands, and a script.

### Single Command

A basic command means that the command that is entered in the command will translate to what gets executed.
In this example we will demonstrate writing the `config` command for `Poseidon` which simply returns the host
information of the target.

1. The first step is to create the file. The file must be placed under the `commands` folder and be named after the
   command.

    ```markdown
    mythic_console
    ├── agents
    │ ├── Poseidon
    │ │ ├── commands
    │ │ │ ├── __init__.py
    │ │ │ ├── config.py
    ```

2. In `config.py`, add the template to get started. Commands are dynamically imported so it is important that the class
   name is the name of the file and starts with a capital letter.

    ```python
    import argparse
    from typing import List, Dict
    
    from cmd2 import cmd2, Cmd2ArgumentParser
    
    from backend import Task
    from backend.mythic_agent.mythic_agent import AgentCommand, MythicAgent, AgentCommandAlias, add_default_options
    
    config_parser = Cmd2ArgumentParser(description="View current config and host information")
    add_default_options(config_parser) # Adds `-bg`/`--background` as options
    
    
    class Config(AgentCommand):
        def __init__(self, agent: MythicAgent):
            super().__init__(agent)
            self._name = "config"
            self._subcommand_parsers: Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser] = {}
            self._aliases = []
    
        @property
        def name(self) -> str:
            return self._name
    
        @property
        def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
            return self._subcommand_parsers
    
        @property
        def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
            return config_parser
    
        @property
        def aliases(self) -> List[AgentCommandAlias]:
            return self._aliases
   
       @cmd2.with_argparser(config_parser)
       def do_config(self, args: argparse.Namespace | str) -> Task:
           pass
    ```

3. Add command logic. Commands are defined leveraging [cmd2](https://cmd2.readthedocs.io/en/stable/) meaning the command
   to be executed must be prefaced with `do_`. The function will return a `Task` object the application will call the
   `execute` method on. The reason why the `args` parameter is either a `argparse.Namespace` object or a `str` is if the
   function is called natively (through the prompt), args will be passed as an `argparse.Namespace` object. If you want
   the command to be available to scripting, it's easier to call the function and pass the args as a string.

   ```python
   def do_config(self, args: argparse.Namespace | str) -> Task:
       # parse the args if they are passed as a string
       if isinstance(args, str):
           args = config_parser.parse_args(args)
  
       # instantiate the Task object
       task = Task(self._agent.instance, command="config",
                   callback_display_id=self._agent.tasker.callback.display_id)
  
       # Arguments that are passed to the command are stored in the task so they may be accessed when formatting.
       # This allows a lot of flexibility to be able to manipulate the data that is returned from Mythic when displaying it.
       # For example, you may choose to sort a column of data based on a field or filter the data that is displayed.
       task.console_args = args
   
       # set background to true if passed. This will release the prompt immediately and continue to run the task
       # output will not be displayed automatically but can be shown by double-clicking the task in the task table
       # when it is competed
       task.background = args.background
       
       return task
   ```

4. Update formatter class. Because `config` just returns a string of a json object, we can leverage the inherited
   `format_pretty`
   method to render our output.

   ```python
   class PoseidonFormatter(Formatter):
       async def format_output(self, task: Task) -> Optional["RenderableType"]:
           command = task.command_name
   
           match command:
               case "pwd":
                   return await self.format_plaintext(task)
               case "shell":
                   return await self.format_plaintext(task)
               case "cat":
                   return await self.format_plaintext(task)
               case "cd":
                   return await self.format_plaintext(task)
               case "config":
                   return await self.format_pretty(task)
   ```

### Grouped Commands

When commands can be grouped together, we can have a parent command and sub-commands to define each command. This will
reduce the number of files you need to create and the amount of boilerplate code you will need to write. Because the
idea of having users type a <command> + <subcommand> can be tedious/you may want command names to match what the agent
command actually is, aliases can be leveraged. In this example, we will implement the copy (cp) command from Poseidon.
Because there are other commands that revolve around a file such as move, delete, etc, this is a perfect use-case for
sub-commands.

1. The first step is to create the file. The file must be placed under the `commands` folder and be named after the
   command. Our parent command will be `file` so our filename will be `file.py`

    ```markdown
    mythic_console
    ├── agents
    │ ├── Poseidon
    │ │ ├── commands
    │ │ │ ├── __init__.py
    │ │ │ ├── file.py
    ```

2. Add boilerplate code to start a new `AgentCommand` and define the argument parsers and commands.

   ```python
   import argparse
   from typing import List, Dict
   
   from cmd2 import cmd2, Cmd2ArgumentParser, argparse_custom, as_subcommand_to
   
   from backend import Task
   from backend.mythic_agent.mythic_agent import AgentCommand, AgentCommandAlias, MythicAgent, add_default_options
   
   # main parser for the file command
   file_parser = Cmd2ArgumentParser()
   file_subparsers = file_parser.add_subparsers(title='subcommands', help='subcommand help')   
   
   # subcommand parser for copy
   file_copy_parser = file_subparsers.add_parser('copy', help='Copy a file')
   file_copy_parser.add_argument('source', help='source path')
   file_copy_parser.add_argument('destination', help='destination path')
   add_default_options(file_copy_parser)
   
   class File(AgentCommand):
       def __init__(self, agent: MythicAgent):
           super().__init__(agent=agent)
           self._name = "file"
   
           # set the subcommand parser, this is used for tab completion
           self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
               "copy": file_copy_parser,
           }
   
           # create an alias so users can use the same command as defined in the agent
           self._aliases = [
               AgentCommandAlias("cp", self._name, "copy")
           ]
   
       @property
       def name(self) -> str:
           return self._name
   
       @property
       def aliases(self) -> List[AgentCommandAlias]:
           return self._aliases
   
       @property
       def subcommand_parsers(self) -> Dict[str, cmd2.argparse_custom.Cmd2ArgumentParser]:
           return self._subcommand_parsers
   
       @property
       def command_parser(self) -> cmd2.argparse_custom.Cmd2ArgumentParser:
           return file_parser
   
       # define main command function which will call the subcommand function 
       @cmd2.with_argparser(file_parser)
       def do_file(self, args):
           func = getattr(args, 'func', None)
           if func is not None:
               return func(self, args)
   
         # define the task for copy
        def file_copy(self, args: argparse.Namespace | str) -> Task:
           if isinstance(args, str):
               args = file_copy_parser.parse_args(args)
   
           command_args = {
               "source": args.source,
               "destination": args.destination
           }
   
           task = Task(self._agent.instance, command="cp", args=command_args,
                       callback_display_id=self._agent.tasker.callback.display_id)
   
           task.console_args = args
           task.background = args.background
           return task
   
       # set the function to call for copy
       file_copy_parser.set_defaults(func=file_copy)
   ```

3. Last part is to define the formatter. Because copy just returns a plaintext string, we can use the inherited
   `format_plaintext` method.

   ```python
   class PoseidonFormatter(Formatter):
       async def format_output(self, task: Task) -> Optional["RenderableType"]:
           command = task.command_name
   
           match command:
               case "pwd":
                   return await self.format_plaintext(task)
               case "shell":
                   return await self.format_plaintext(task)
               case "cat":
                   return await self.format_plaintext(task)
               case "cd":
                   return await self.format_plaintext(task)
               case "config":
                   return await self.format_pretty(task)
               case "cp":
                   return await self.format_plaintext(task)
               case "ls":
                   return await self.format_ls(task)
               case _:
                   raise FormatterNotAvailable(command)
   ```

4. Just to emphasize, let's add another subcommand. In this step we will implement the `cat` command.

    1. Add new subcommand parser for `cat`
       ```python
       file_cat_parser = file_subparsers.add_parser('cat', help='Cat a file')
       file_cat_parser.add_argument('path', nargs='+', help='Path to file to cat')
       add_default_options(file_cat_parser)
       ```
    2. Create method for creating the task
        ```python
            def file_cat(self, args: str | argparse.Namespace) -> Task:
                if isinstance(args, str):
                    subcommand_parser = file_cat_parser
                    args = subcommand_parser.parse_args(args)
        
                path = " ".join(args.path)
                task = Task(self._agent.instance, command="cat", args=path,
                            callback_display_id=self._agent.tasker.callback.display_id)
        
                task.console_args = args
                task.background = args.background
                return task
        
            file_cat_parser.set_defaults(func=file_cat)
        ```
    3. Update alias/subcommand parsers
         ```python
             def __init__(self, agent: MythicAgent):
                 super().__init__(agent=agent)
                 self._name = "file"
                 self._subcommand_parsers: Dict[str, argparse_custom.Cmd2ArgumentParser] = {
                     "copy": file_copy_parser,
                     "cat": file_cat_parser,
                 }
                 self._aliases = [
                     AgentCommandAlias("cp", self._name, "copy"),
                     AgentCommandAlias("cat", self._name, "cat")
                 ]
         ```

## Create a `Formatter` for your Agent.

The `Formatter` class is an Abstract Base Class that can be used to customize how you want your commands results to
appear in the console.
Each method can do whatever you want but should return
a [Rich RenderableType](https://rich.readthedocs.io/en/stable/reference/console.html?highlight=renderabletype#rich.console.RenderableType).
The base `Formatter` class comes with a few methods for free to including a method to print a plaintext response among
others.

If creating your own formatter, you only are required to define one method: `format_output`.
This method takes in one parameter of type `Task` which is the task executed.
If you defined your task to have arguments to customize how the results should look, these values will be available in
the task under `task.console_args`.

Here is an example of a sample formatter.

```python
from backend import Formatter, Task
from utils.environment import Environment

import os
import json
from rich.text import Text
from rich.table import Table
from typing import Optional


class NewAgentFormatter(Formatter):
    async def format_output(self, task: Task) -> Optional["RenderableType"]:
        command = task.command_name

        match command:
            case "command1":
                return await self.format_pretty(task)
            case "command2":
                return await self.format_plaintext(task)
            case "command3":
                return await self.command3(task)
            case "download":
                return await self.download(task)

    async def command3(self, task: Task, encoding: str = "utf8") -> Table | Text:
        raw = await self.get_raw_output(task, encoding)

        try:
            results = json.loads(raw)
        except json.JSONDecodeError:
            return Text(raw)

        rows = []
        headers = ["col1", "col2", "col3"]

        title = "Command 3 Output"
        for result in results:
            foo = result.get("foo")
            bar = result.get("bar")
            rows.append([foo, bar])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    @classmethod
    async def download(cls, task: Task) -> Text:
        success = False
        local_path = ""
        try:
            filename = task.params.replace(" ", "_")
            download_dir = os.path.join(Environment().download_directory(),
                                        f"{task.hostname}_{task.callback_display_id}")
            if not os.path.isdir(download_dir):
                os.makedirs(download_dir, exist_ok=True)

            local_path = os.path.join(download_dir, filename)
            success = await task.download_file(local_path)
        except Exception as e:
            return Text(f"failed to download file: {e}")
        finally:
            if success and local_path:
                return Text(f"[+] file successfully saved to {local_path}")

            return Text("failed to download file")
```
