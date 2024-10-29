import json
import os.path
from typing import Optional

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text

import utils
from backend import Formatter, Task
from utils.environment import Environment
from utils.logger import logger


class PoseidonFormatter(Formatter):
    async def format_output(self, task: Task) -> Optional["RenderableType"]:
        command = task.command_name

        match command:
            case "config":
                return await self.format_pretty(task)
            case "download":
                return await self.download(task)
            case "drives":
                return await self.drives(task)
            case "execute_library":
                return await self.get_env(task)
            case "getuser":
                return await self.format_pretty(task, expand_all=True)
            case "jobs":
                return await self.jobs(task)
            case "keys":
                return await self.format_pretty(task, expand_all=True)
            case "ls":
                return await self.ls(task)
            case "portscan":
                return await self.portscan(task)
            case "ps":
                return await self.ps(task)
            case "sshauth":
                return await self.ssh_auth(task)
            case _:
                return await self.format_plaintext(task)

    async def ls(self, task: Task, encoding: str = "utf8") -> Table | Text:
        raw = await self.get_raw_output(task, encoding)

        try:
            output = json.loads(raw)
        except json.JSONDecodeError:
            return Text(raw)

        rows = []
        headers = ["permissions", "user", "size", "path"]

        full_path = f"{output.get('parent_path') or ''}/{output.get('name')}"
        title = f"ls of {full_path}"
        is_file = output.get('is_file')
        permissions = output.get('permissions').get('permissions')
        size = output.get('size')
        user = output.get('permissions').get('user')
        rows.append([permissions, user, str(size) if is_file else "", full_path])

        for f in output.get("files") or []:
            full_path = f.get('full_name')
            is_file = f.get('is_file')
            permissions = f.get('permissions').get('permissions')
            size = f.get('size')
            user = f.get('permissions').get('user')

            rows.append([permissions, user, str(size) if is_file else "", full_path])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    @classmethod
    async def download(cls, task: Task) -> Text:
        success = False
        local_path = ""
        try:
            filename = task.params.replace(" ", "_")
            timestamped_name = f"{utils.get_timestamp()}_{filename}"
            download_dir = os.path.join(Environment().download_directory(),
                                        f"{task.hostname}_{task.callback_display_id}")
            if not os.path.isdir(download_dir):
                os.makedirs(download_dir, exist_ok=True)

            local_path = os.path.join(download_dir, timestamped_name.replace("/", "_"))
            success = await task.download_file(local_path)
        except Exception as e:
            return Text(f"failed to download file: {e}")
        finally:
            if success and local_path:
                return Text(f"[+] file successfully saved to {local_path}")

            return Text("failed to download file")

    async def drives(self, task: Task, encoding: str = "utf8") -> Table:
        raw = await self.get_raw_output(task, encoding)

        drives = json.loads(raw)
        rows = []
        headers = ["name", "description", "free", "total"]

        title = "drives"
        for drive in drives:
            name = drive.get("name")
            desc = drive.get("description")
            free = drive.get("free_bytes_pretty")
            total = drive.get("total_bytes_pretty")
            rows.append([name, desc, free, total])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    async def get_env(self, task: Task) -> Table:
        raw = await self.get_raw_output(task)

        variables = raw.split("\n")
        rows = []
        headers = ["parameter", "value"]

        title = "Environment Variables"
        for env in variables:
            tokens = env.split("=")
            if len(tokens) < 1:
                continue

            param = tokens[0]
            if len(tokens) == 1:
                rows.append([param, ""])
                continue

            value = "=".join(tokens[1:])
            rows.append([param, value])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    async def jobs(self, task: Task, encoding: str = "utf8") -> Table:
        raw = await self.get_raw_output(task, encoding)

        drives = json.loads(raw)
        rows = []
        headers = ["command", "params", "uuid"]

        title = "Running Jobs"
        for drive in drives:
            command = drive.get("command")
            params = drive.get("params")
            uuid = drive.get("id")
            rows.append([command, params, uuid])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    async def portscan(self, task: Task, encoding: str = "utf8") -> Table:
        raw = await self.get_raw_output(task, encoding)

        results = json.loads(raw)
        rows = []
        headers = ["host", "open ports"]

        title = "Scan Results"
        for result in results:
            hosts = result.get("hosts") or []
            for host in hosts:
                name = host.get("pretty_name")
                open_ports = host.get("open_ports") or ""
                if open_ports:
                    open_ports = " ".join(map(str, open_ports))
                rows.append([name, open_ports])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    async def ps(self, task: Task, encoding: str = "utf8") -> Table:
        raw = await self.get_raw_output(task, encoding)

        processes = json.loads(raw) or []
        rows = []
        headers = ["PID", "PPID", "Arch", "User", "Name"]

        title = "Process List"
        for process in processes:
            pid = process.get("process_id") or ""
            ppid = process.get("parent_process_id") or ""
            arch = process.get("architecture") or ""
            user = process.get("user") or ""
            name = process.get("name") or ""
            rows.append([str(pid), str(ppid), arch, user, name])

        table = self.build_table(*rows, headers=headers, title=title)
        return table

    async def ssh_auth(self, task: Task, encoding: str = "utf8") -> Table:
        raw = await self.get_raw_output(task, encoding)

        results = json.loads(raw) or []
        rows = []
        headers = ["Host", "Username", "Secret", "Copy Status", "Output"]

        title = "SSH Execution"
        for result in results:
            host = result.get("host") or ""
            username = result.get("username") or ""
            secret = result.get("secret") or ""
            copy = result.get("copy_status") or ""
            output = result.get("output") or ""
            rows.append([host, username, secret, copy, output])

        table = self.build_table(*rows, headers=headers, title=title)
        return table
