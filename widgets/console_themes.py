from rich.style import Style
from textual._text_area_theme import TextAreaTheme

MYTHIC_DARK = TextAreaTheme(
    name="mythic_dark",
    base_style=Style(color="#CCCCCC", bgcolor="#1F1F1F"),
    gutter_style=Style(color="#6E7681", bgcolor="#1F1F1F"),
    cursor_style=Style(color="#CCCCCC", bgcolor="#1F1F1F"),
    cursor_line_style=Style(bgcolor="#1F1F1F"),
    bracket_matching_style=Style(bgcolor="#3a3a3a", bold=True),
    cursor_line_gutter_style=Style(color="#CCCCCC", bgcolor="#2b2b2b"),
    selection_style=Style(bgcolor="#264F78"),
)

MYTHIC_LIGHT = TextAreaTheme(
    name="mythic_light",
    base_style=Style(color="#24292e", bgcolor="#f0f0f0"),
    gutter_style=Style(color="#BBBBBB", bgcolor="#f0f0f0"),
    cursor_style=Style(color="#24292e", bgcolor="#f0f0f0"),
    cursor_line_style=Style(bgcolor="#f0f0f0"),
    bracket_matching_style=Style(color="#24292e", underline=True),
    cursor_line_gutter_style=Style(color="#A4A4A4", bgcolor="#ebebeb"),
    selection_style=Style(bgcolor="#c8c8fa"),
)
