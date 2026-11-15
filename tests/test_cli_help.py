import pytest

import mythic_console.console as console
from mythic_console.console import build_arg_parser
from mythic_console.version import __version__


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_flag_exits_zero_and_prints_usage(flag, capsys):
    with pytest.raises(SystemExit) as exc:
        build_arg_parser().parse_args([flag])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "usage:" in out
    assert "Mythic C2" in out


def test_help_lists_env_vars(capsys):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--help"])

    out = capsys.readouterr().out
    assert "MYTHIC_SERVER_URL" in out
    assert "LOG_LEVEL" in out


def test_help_lists_plugin_subcommands(capsys):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--help"])

    out = capsys.readouterr().out
    assert "install" in out
    assert "plugin" in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        build_arg_parser().parse_args(["--version"])

    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_parses_without_error():
    args = build_arg_parser().parse_args([])

    assert args.action is None


@pytest.mark.parametrize("argv", [["--bogus"], ["bogus"]])
def test_unknown_argument_exits_nonzero(argv):
    with pytest.raises(SystemExit) as exc:
        build_arg_parser().parse_args(argv)

    assert exc.value.code != 0


def test_plugin_subcommand_namespace():
    args = build_arg_parser().parse_args(["plugin", "list"])

    assert args.action == "plugin"
    assert args.plugin_action == "list"


def test_help_does_not_launch_app(monkeypatch):
    launched = {"run": False}

    class FakeApp:
        def run(self):
            launched["run"] = True

    monkeypatch.setattr(console, "MythicConsole", FakeApp)
    monkeypatch.setattr(console.sys, "argv", ["mythic-console", "--help"])

    with pytest.raises(SystemExit) as exc:
        console.main()

    assert exc.value.code == 0
    assert launched["run"] is False


def test_no_args_launches_app(monkeypatch):
    launched = {"run": False}

    class FakeApp:
        def run(self):
            launched["run"] = True

    monkeypatch.setattr(console, "MythicConsole", FakeApp)
    monkeypatch.setattr(console.sys, "argv", ["mythic-console"])

    console.main()

    assert launched["run"] is True


def test_plugin_subcommand_routes_to_dispatch(monkeypatch):
    seen = {}

    def fake_dispatch(args):
        seen["action"] = args.action
        return 0

    monkeypatch.setattr(console, "dispatch_plugin", fake_dispatch)
    monkeypatch.setattr(console, "MythicConsole", object)
    monkeypatch.setattr(console.sys, "argv", ["mythic-console", "plugin", "list"])

    with pytest.raises(SystemExit) as exc:
        console.main()

    assert exc.value.code == 0
    assert seen["action"] == "plugin"
