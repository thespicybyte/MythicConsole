import logging
import os


class Environment:
    def username(self) -> str | None:
        """check environment variables for `MYTHIC_CONSOLE_USER`"""
        return os.getenv("MYTHIC_CONSOLE_USER") or self.get_value_from_config("MYTHIC_CONSOLE_USER")

    def password(self) -> str | None:
        """check environment variables for `MYTHIC_CONSOLE_PASSWORD`"""
        return os.getenv("MYTHIC_CONSOLE_PASSWORD") or self.get_value_from_config("MYTHIC_CONSOLE_PASSWORD")

    def server_url(self) -> str | None:
        """check environment variables for `MYTHIC_SERVER_URL`"""
        return os.getenv("MYTHIC_SERVER_URL") or self.get_value_from_config("MYTHIC_SERVER_URL")

    def download_directory(self) -> str:
        """
        check environment variables for `DOWNLOAD_DIRECTORY`.
        Returns current directory/downloads if not set
        """
        download_dir = os.getenv("DOWNLOAD_DIRECTORY") or self.get_value_from_config("DOWNLOAD_DIRECTORY")
        if download_dir:
            if not os.path.isdir(download_dir):
                os.makedirs(download_dir, exist_ok=True)
            return download_dir
        return os.path.join(os.getcwd(), "downloads")

    def log_directory(self) -> str:
        """
        check environment variables for `LOG_DIRECTORY`.
        Returns current directory if not set
        """
        log_dir = os.getenv("LOG_DIRECTORY") or self.get_value_from_config("LOG_DIRECTORY")
        if log_dir:
            if not os.path.isdir(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            return log_dir
        return os.getcwd()

    def log_file(self) -> str:
        """
        check environment variables for `LOG_FILE`.
        Returns `.console.log` if not set
        """
        log_file = os.getenv("LOG_FILE") or self.get_value_from_config("LOG_FILE")
        if log_file:
            return log_file
        return ".console.log"

    def log_level(self) -> int:
        """
        check environment variables for `LOG_LEVEL`.
        Valid options are `debug`, `info`, `warning`, `error`, `none`
        Returns NOTSET if not set
        """
        log_level = os.getenv("LOG_LEVEL") or self.get_value_from_config("LOG_LEVEL")
        if not log_level:
            log_level = "info"

        match log_level.lower():
            case "debug":
                return logging.DEBUG
            case "info":
                return logging.INFO
            case "warn":
                return logging.WARNING
            case "warning":
                return logging.WARNING
            case "error":
                return logging.ERROR
            case _:
                return logging.NOTSET

    @classmethod
    def get_value_from_config(cls, value: str) -> str | None:
        if not os.path.isfile(".env"):
            return None

        with open(".env", 'r') as f:
            config = f.readlines()

        for line in config:
            tokens = line.strip().split("=")
            if len(tokens) < 2:
                continue

            key = tokens[0].strip()
            if key != value:
                continue

            env_value = "=".join(tokens[1:])
            return env_value
