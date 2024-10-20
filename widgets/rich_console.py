from typing import cast

from rich.console import RenderableType
from rich.highlighter import Highlighter, ReprHighlighter
from rich.measure import measure_renderables
from rich.pretty import Pretty
from rich.protocol import is_renderable
from rich.segment import Segment
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.cache import LRUCache
from textual.document._document import Location, DocumentBase, Document
from textual.document._wrapped_document import WrappedDocument
from textual.events import MouseEvent, Timer
from textual.geometry import Size, Offset
from textual.message import Message
from textual.reactive import var
from textual.strip import Strip
from textual.widget import Widget

from typing_extensions import Self

from utils.logger import logger


class TextAreaHideCompletionList(Message):
    pass


class RichConsole(Widget, can_focus=True, can_focus_children=False):
    DEFAULT_CSS = """
    RichLog{
        background: $surface;
        color: $text;
        overflow-y: scroll;
    }
    """

    BINDINGS = [
        Binding("ctrl+f", "find", "Find"),
        Binding("f3", "find(True)", "Find Next"),
    ]

    auto_scroll: var[bool] = var(True)
    min_width: var[int] = var(78)
    wrap: var[bool] = var(False)
    markup: var[bool] = var(False)

    def __init__(
            self,
            *children: Widget,
            name: str | None = None,
            id: str | None = None,  # noqa: A002
            classes: str | None = None,
            disabled: bool = False,
            use_system_clipboard: bool = True,
            min_width: int = 78,
            wrap: bool = False,
            markup: bool = False,
            auto_scroll: bool = True,
            highlight: bool = False,

    ) -> None:
        """
        Initializes an mythic_instance of a TextArea.

        Args:
            (see also textual.widget.Widget)
            language (str): Must be the short name of a Pygments lexer
                (https://pygments.org/docs/lexers/), e.g., "python", "sql", "as3".
            theme (str): Must be name of a Pygments style (https://pygments.org/styles/),
                e.g., "bw", "github-dark", "solarized-light".
        """
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )

        self.use_system_clipboard = use_system_clipboard
        self.lines: list[Strip] = []
        self.min_width = min_width
        self.markup = markup
        self.auto_scroll = auto_scroll
        self.wrap = wrap
        self._start_line: int = 0
        self._last_container_width: int = min_width
        self._line_cache: LRUCache[tuple[int, int, int, int], Strip]
        self._line_cache = LRUCache(1024)
        self.max_width: int = 0
        self.highlight = highlight
        self.highlighter: Highlighter = ReprHighlighter()
        self.double_click_location: Location | None = None
        self.double_click_timer: Timer | None = None
        self.consecutive_clicks: int = 0

        self.document: DocumentBase = Document("")
        """The document this widget is currently editing."""

        self.wrapped_document: WrappedDocument = WrappedDocument(self.document)
        """The wrapped view of the document."""

        self._selecting = False
        """True if we're currently selecting text using the mouse, otherwise False."""

    def notify_style_update(self) -> None:
        self._line_cache.clear()

    def on_resize(self) -> None:
        self._last_container_width = self.scrollable_content_region.width

    def _make_renderable(self, content: RenderableType | object) -> RenderableType:
        """Make content renderable.

        Args:
            content: Content to render.

        Returns:
            A Rich renderable.
        """
        renderable: RenderableType
        if not is_renderable(content):
            renderable = Pretty(content)
        else:
            if isinstance(content, str):
                if self.markup:
                    renderable = Text.from_markup(content)
                else:
                    renderable = Text(content)
                if self.highlight:
                    renderable = self.highlighter(renderable)
            else:
                renderable = cast(RenderableType, content)

        if isinstance(renderable, Text):
            renderable.expand_tabs()

        return renderable

    def write(
            self,
            content: RenderableType | object,
            width: int | None = None,
            expand: bool = False,
            shrink: bool = True,
            scroll_end: bool | None = None,
    ) -> Self:
        """Write text or a rich renderable.

        Args:
            content: Rich renderable (or text).
            width: Width to render or `None` to use optimal width.
            expand: Enable expand to widget width, or `False` to use `width`.
            shrink: Enable shrinking of content to fit width.
            scroll_end: Enable automatic scroll to end, or `None` to use `self.auto_scroll`.

        Returns:
            The `RichLog` mythic_instance.
        """

        auto_scroll = self.auto_scroll if scroll_end is None else scroll_end

        console = self.app.console
        render_options = console.options

        renderable = self._make_renderable(content)

        if isinstance(renderable, Text) and not self.wrap:
            render_options = render_options.update(overflow="ignore", no_wrap=True)

        render_width = measure_renderables(
            console, render_options, [renderable]
        ).maximum

        container_width = (
            self.scrollable_content_region.width if width is None else width
        )

        # Use the container_width if it's available, otherwise use the last available width.
        container_width = (
            container_width if container_width else self._last_container_width
        )

        if expand and render_width < container_width:
            render_width = container_width
        if shrink and render_width > container_width:
            render_width = container_width

        render_width = max(render_width, self.min_width)

        segments = self.app.console.render(
            renderable, render_options.update_width(render_width)
        )
        lines = list(Segment.split_lines(segments))
        if not lines:
            self.lines.append(Strip.blank(render_width))
        else:
            self.max_width = max(
                self.max_width,
                max(sum([segment.cell_length for segment in _line]) for _line in lines),
            )
            strips = Strip.from_lines(lines)
            for strip in strips:
                strip.adjust_cell_length(render_width)
            self.lines.extend(strips)

        self.virtual_size = Size(self.max_width, len(self.lines))
        if auto_scroll:
            self.scroll_end(animate=False)

        return self

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        line = self._render_line(scroll_y + y, scroll_x, self.size.width)
        strip = line.apply_style(self.rich_style)
        return strip

    def _render_line(self, y: int, scroll_x: int, width: int) -> Strip:
        if y >= len(self.lines):
            return Strip.blank(width, self.rich_style)

        key = (y + self._start_line, scroll_x, width, self.max_width)
        if key in self._line_cache:
            return self._line_cache[key]

        line = self.lines[y].crop_extend(scroll_x, scroll_x + width, self.rich_style)

        self._line_cache[key] = line
        return line

    def get_target_document_location(self, event: MouseEvent) -> Location:
        """Given a MouseEvent, return the row and column offset of the event in document-space.

        Args:
            event: The MouseEvent.

        Returns:
            The location of the mouse event within the document.
        """
        scroll_x, scroll_y = self.scroll_offset
        target_x = event.x + scroll_x - self.gutter.left
        target_y = event.y + scroll_y - self.gutter.top
        location = self.wrapped_document.offset_to_location(Offset(target_x, target_y))
        return location

    def on_mouse_down(self, event: events.MouseDown) -> None:
        target = self.get_target_document_location(event)
        logger.info(target)
        if (
                self.double_click_location is not None
                and self.double_click_location == target
        ):
            event.prevent_default()
            self._selecting = True
            self.capture_mouse()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        target = self.get_target_document_location(event)
        if (
                self.consecutive_clicks > 0
                and self.double_click_location is not None
                and self.double_click_location == target
        ):
            if self.consecutive_clicks == 1:
                self.action_select_word()
            elif self.consecutive_clicks == 2:
                self.action_select_line()
                self.action_cursor_right(select=True)
            else:
                self.action_select_all()
            self.consecutive_clicks += 1
        else:
            self.history.checkpoint()
            self.double_click_location = target
            self.consecutive_clicks += 1

        if self.double_click_timer is not None:
            self.double_click_timer.reset()
        else:
            self.double_click_timer = self.set_timer(
                delay=0.5, callback=self._clear_double_click, name="double_click_timer"
            )

    def action_select_word(self) -> None:
        self.post_message(TextAreaHideCompletionList())
        prev = self._get_character_before_cursor()
        next_char = self._get_character_at_cursor()
        at_start_of_word = self._word_pattern.match(prev) is None
        at_end_of_word = self._word_pattern.match(next_char) is None
        if at_start_of_word and not at_end_of_word:
            self.action_cursor_word_right(select=True)
        elif at_end_of_word and not at_start_of_word:
            self.action_cursor_word_left(select=True)
            self.section = Selection(start=self.selection.end, end=self.selection.start)
        else:
            self.action_cursor_word_left(select=False)
            self.action_cursor_word_right(select=True)

    def _get_character_before_cursor(self) -> str:
        if self.cursor_at_start_of_line:
            return ""
        return self.get_text_range(
            start=self.get_cursor_left_location(), end=self.cursor_location
        )
