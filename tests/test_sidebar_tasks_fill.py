from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from widgets.callbacks import Callbacks
from widgets.tasks_table import TasksTable

CSS_PATH = Path(__file__).resolve().parent.parent / "mythic.tcss"


class _Harness(App):
    CSS_PATH = CSS_PATH

    def __init__(self, instance):
        super().__init__()
        self._instance = instance
        self.scroll: VerticalScroll | None = None
        self.callbacks_module: Callbacks | None = None
        self.tasks_module: TasksTable | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll() as self.scroll:
            spacer = Static("")
            spacer.styles.height = 15
            spacer.styles.margin = 1
            yield spacer
            self.callbacks_module = Callbacks(self._instance)
            yield self.callbacks_module
            self.tasks_module = TasksTable(self._instance)
            yield self.tasks_module


async def test_tasks_table_grows_past_old_cap(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        assert app.tasks_module.region.height > 12


async def test_tasks_table_fills_to_scroll_bottom(fake_instance):
    app = _Harness(fake_instance)
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        assert abs(app.tasks_module.region.bottom - app.scroll.region.bottom) <= 1


async def test_tasks_table_tracks_window_height(fake_instance):
    tall_app = _Harness(fake_instance)
    async with tall_app.run_test(size=(100, 50)) as pilot:
        await pilot.pause()
        tall_height = tall_app.tasks_module.region.height

    short_app = _Harness(fake_instance)
    async with short_app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        short_height = short_app.tasks_module.region.height

    assert tall_height > short_height


async def test_callbacks_module_height_unchanged(fake_instance):
    for size in [(100, 50), (100, 30)]:
        app = _Harness(fake_instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert app.callbacks_module.region.height == 12
