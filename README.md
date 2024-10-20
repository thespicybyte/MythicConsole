# Mythic Console

Mythic Console is a terminal user interface that can be used to interact
with [Mythic C2](https://github.com/its-a-feature/Mythic).
Mythic Console is not designed to replace the web interface but rather provide an alternate interface to experience for
users to interact with callbacks and operations.

> [!NOTE]
> This is a pre-release under in active development.

# Quick Start

## Requirements

Mythic Console requires python 3.8 or greater.

## Installation

```shell
git clone https://github.com/thespicybyte/MythicConsole.git
cd MythicConsole
python -m venv venv

# linux
source venv/bin/activate

# windows
.\venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

No other configuration is required but there are a couple ways to speed up authentication.
When you start the application, the user will be prompted for the username, password, and server.
These three values may be passed in and populated for you based on environment variables or the `.env` config file.
Other variables may be passed to further configure your environment.

| Name                    | Description                                                                                         |
|-------------------------|-----------------------------------------------------------------------------------------------------|
| MYTHIC_CONSOLE_USER     | Populates the username field                                                                        |
| MYTHIC_CONSOLE_PASSWORD | Populates the password field                                                                        |
| MYTHIC_SERVER_URL       | Populates the server field                                                                          |
| DOWNLOAD_DIRECTORY      | Configures the base directory where files downloaded from Mythic are stored                         |
| LOG_DIRECTORY           | Set the  directory logs are stored in. Default is cwd                                               |
| LOG_FILE                | Set the log  file. Default is .console.log                                                          |
| LOG_LEVEL               | Set the log level. Available options are `debug`, `info`, `warning`, and `error`. Default is `info` |

## Execution

```
python console.py
```

## Adding Commands

Agent commands are simple to write and allow the author a lot of flexibility.
All commands must inherit the `AgentCommand` class which in
an [Abstract Base Class](https://docs.python.org/3/library/abc.html), or interface, the provides all the plumbing
necessary to subcommands, aliases, and tab completion. There are three ways to define an Agent Command: basic command,
command with sub-commands, and a script.

### Basic Command

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
       