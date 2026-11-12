import importlib.resources

from textual.app import App, ComposeResult

from mythic_console.backend.mythic_agent.mythic_agent import MythicCommands
from mythic_console.widgets.console import ConsolePanel

CSS_PATH = str(importlib.resources.files("mythic_console") / "mythic.tcss")


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.panel: ConsolePanel | None = None

    def compose(self) -> ComposeResult:
        self.panel = ConsolePanel(instance=self._instance)
        yield self.panel


async def test_output_does_not_overlap_input(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test(size=(100, 30)) as pilot:
        for i in range(50):
            app.panel.write_string(f"line {i}")
        await pilot.pause()

        output_region = app.panel.console_output.region
        input_region = app.panel.console_input.region

        assert output_region.bottom <= input_region.y
        assert input_region.bottom <= app.screen.region.bottom
        assert output_region.height >= 3


async def test_on_mount_seeds_operation_cache(fake_instance, monkeypatch):
    calls = []

    async def fake_cache_operations(self):
        calls.append(True)

    monkeypatch.setattr(MythicCommands, "cache_operations", fake_cache_operations)

    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert calls == [True]


async def test_on_mount_seeds_blocklist_caches(fake_instance, monkeypatch):
    calls = []

    async def fake_cache_blocklists(self):
        calls.append("blocklists")

    async def fake_cache_blocklist_commands(self):
        calls.append("blocklist_commands")

    monkeypatch.setattr(MythicCommands, "cache_blocklists", fake_cache_blocklists)
    monkeypatch.setattr(MythicCommands, "cache_blocklist_commands", fake_cache_blocklist_commands)

    app = _Harness(fake_instance)
    async with app.run_test() as pilot:
        await pilot.pause()

        assert set(calls) == {"blocklists", "blocklist_commands"}
