import sys
from pathlib import Path
from textwrap import dedent

import pytest

from plugins.registry import get_plugin_registry


def _build_plugin_package(tmp_path: Path, pkg_name: str, script_files: dict) -> None:
    """Writes a minimal on-disk PluginAgent package with the given scripts/<name>.py -> source map."""
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "agent.py").write_text(dedent("""
        from plugins.base import PluginAgent


        class Agent(PluginAgent):
            def __init__(self, instance):
                super().__init__("testtype", instance, None)
    """))

    scripts_dir = pkg_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")
    for filename, source in script_files.items():
        (scripts_dir / filename).write_text(dedent(source))

    sys.path.insert(0, str(tmp_path))


def _make_agent(pkg_name: str, fake_instance):
    import importlib
    module = importlib.import_module(f"{pkg_name}.agent")
    return module.Agent(fake_instance)


def test_script_discovered_by_type_not_name(tmp_path, fake_instance):
    _build_plugin_package(tmp_path, "pkg_bytype", {
        "foo.py": """
            from backend.mythic_agent.mythic_agent import ScriptCommand

            class WhateverName(ScriptCommand):
                pass
        """,
    })

    agent = _make_agent("pkg_bytype", fake_instance)
    scripts = agent.get_script_classes()

    assert [type(s).__name__ for s in scripts] == ["WhateverName"]


def test_module_with_no_scriptcommand_subclass_contributes_nothing(tmp_path, fake_instance):
    _build_plugin_package(tmp_path, "pkg_noscript", {
        "bar.py": """
            def helper():
                return "not a command"
        """,
    })

    agent = _make_agent("pkg_noscript", fake_instance)
    scripts = agent.get_script_classes()

    assert scripts == []


def test_imported_scriptcommand_base_not_picked_up(tmp_path, fake_instance):
    _build_plugin_package(tmp_path, "pkg_importedbase", {
        "baz.py": """
            from backend.mythic_agent.mythic_agent import ScriptCommand
        """,
    })

    agent = _make_agent("pkg_importedbase", fake_instance)
    scripts = agent.get_script_classes()

    assert scripts == []


def test_two_subclasses_in_one_module_both_load(tmp_path, fake_instance):
    _build_plugin_package(tmp_path, "pkg_multi", {
        "multi.py": """
            from backend.mythic_agent.mythic_agent import ScriptCommand

            class FirstScript(ScriptCommand):
                pass

            class SecondScript(ScriptCommand):
                pass
        """,
    })

    agent = _make_agent("pkg_multi", fake_instance)
    scripts = agent.get_script_classes()

    assert {type(s).__name__ for s in scripts} == {"FirstScript", "SecondScript"}


def test_testplugin_fixture_ping_still_loads(fake_instance, installed_testplugin):
    agent_class = get_plugin_registry().agent_class_for("testplugin")
    agent = agent_class(fake_instance)

    scripts = agent.get_script_classes()

    assert any(s.name == "ping" for s in scripts)
