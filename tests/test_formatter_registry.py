from rich.text import Text

from backend.formatter.formatter import DefaultFormatter, Formatter, renders


def test_plugin_formatter_is_registered_via_import(test_plugin_agent):
    """A plugin's formatter registers itself with the formatter registry simply by being
    imported when its agent module is loaded -- no extra wiring needed."""
    assert type(test_plugin_agent.formatter)._renderers == {"echo": "echo"}


def test_base_formatter_registry_is_empty():
    assert Formatter._renderers == {}


def test_default_formatter_registry_is_empty():
    assert DefaultFormatter._renderers == {}


async def test_default_formatter_format_output_falls_back_to_plaintext(make_task, fake_responses):
    fake_responses(["raw output"])
    task = make_task(command_name="whatever", completed=True)

    result = await DefaultFormatter().format_output(task)

    assert isinstance(result, Text)
    assert result.plain == "raw output"


def test_subclass_registries_are_isolated():
    class Alpha(Formatter):
        @renders("a")
        async def render_a(self, task):
            return "a"

    class Beta(Formatter):
        @renders("b")
        async def render_b(self, task):
            return "b"

    assert Alpha._renderers == {"a": "render_a"}
    assert Beta._renderers == {"b": "render_b"}
    assert Formatter._renderers == {}


def test_subclass_extends_and_overrides_parent_registry():
    class Parent(Formatter):
        @renders("shared")
        async def render_shared(self, task):
            return "parent"

    class Child(Parent):
        @renders("child_only")
        async def render_child_only(self, task):
            return "child"

        @renders("shared")
        async def render_shared_override(self, task):
            return "child-override"

    assert Child._renderers == {
        "shared": "render_shared_override",
        "child_only": "render_child_only",
    }
    assert Parent._renderers == {"shared": "render_shared"}
