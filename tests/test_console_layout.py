from pathlib import Path

from textual.app import App, ComposeResult

from widgets.console import ConsolePanel

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"


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
