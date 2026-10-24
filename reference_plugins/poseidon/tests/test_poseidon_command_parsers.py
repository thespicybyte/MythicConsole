from backend.mythic_agent.mythic_agent import AgentCommand

_NO_BACKGROUND_FLAG = {"exit"}


async def test_command_parser_carries_background_flag(poseidon_agent):
    for command in poseidon_agent.commands:
        if command.name in _NO_BACKGROUND_FLAG:
            continue

        parsers = list(command.subcommand_parsers.values()) or [command.command_parser]
        for parser in parsers:
            options = AgentCommand.get_parser_options(parser)
            assert "--background" in options, f"{command.name}: {parser.prog} missing -bg/--background"


async def test_flat_command_parse_args_empty_yields_falsy_background(poseidon_agent):
    for command in poseidon_agent.commands:
        if command.subcommand_parsers or command.name in _NO_BACKGROUND_FLAG:
            continue

        required_flags = [action for action in command.command_parser._actions if action.required]
        if required_flags:
            continue

        args = command.command_parser.parse_args([])
        assert not args.background


async def test_exit_opts_out_of_background_flag(poseidon_agent):
    exit_command = poseidon_agent.get_command("exit")
    assert "--background" not in AgentCommand.get_parser_options(exit_command.command_parser)


async def test_sleep_parses_interval_and_jitter(poseidon_agent):
    sleep = poseidon_agent.get_command("sleep")
    args = sleep.command_parser.parse_args(["--interval", "5", "--jitter", "10"])
    assert args.interval == 5
    assert args.jitter == 10


async def test_process_list_subcommand_parses_regex_filter(poseidon_agent):
    process = poseidon_agent.get_command("process")
    parser = process.get_subcommand_parser("list")
    args = parser.parse_args(["--regex", "chrome.*"])
    assert args.regex == "chrome.*"


async def test_command_run_subcommand_parses_shell_command(poseidon_agent):
    command = poseidon_agent.get_command("command")
    parser = command.get_subcommand_parser("run")
    args = parser.parse_args(["echo", "hello"])
    assert args.command == ["echo", "hello"]
