# Mythic Console

Mythic Console is a terminal user interface that can be used to interact
with [Mythic C2](https://github.com/its-a-feature/Mythic).
Mythic Console is not designed to replace the web interface but rather provide an alternate interface to experience for
users to interact with callbacks and operations.

> [!NOTE]
> This is a pre-release under in active development.

# Supported Agents

- Poseidon

# Demo

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

# Extend Mythic Console

Check out [customization page](customize.md) to learn how to extend Mythic Console.

# Road Map

- [ ] Add more Agents
    - [ ] Apollo

