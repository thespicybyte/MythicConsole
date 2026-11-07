from backend.mythic_agent.mythic_agent import AgentCommand


async def test_command_parser_carries_background_flag(arachne_agent):
    for command in arachne_agent.commands:
        parsers = list(command.subcommand_parsers.values()) or [command.command_parser]
        for parser in parsers:
            options = AgentCommand.get_parser_options(parser)
            assert "--background" in options, f"{command.name}: {parser.prog} missing -bg/--background"


async def test_flat_command_parse_args_empty_yields_falsy_background(arachne_agent):
    for command in arachne_agent.commands:
        if command.subcommand_parsers:
            continue

        required_flags = [action for action in command.command_parser._actions if action.required]
        if required_flags:
            continue  # parsing an empty line would raise

        args = command.command_parser.parse_args([])
        assert not args.background


async def test_plugin_curated_grouped_command_subcommand_parses_its_option(test_plugin_agent):
    net = test_plugin_agent.get_command("net")
    parser = net.get_subcommand_parser("echo")
    args = parser.parse_args(["--text", "hi"])
    assert args.text == "hi"


async def test_plugin_curated_grouped_command_second_subcommand_parses_its_option(test_plugin_agent):
    net = test_plugin_agent.get_command("net")
    parser = net.get_subcommand_parser("connect")
    args = parser.parse_args(["--port", "4444"])
    assert args.port == 4444
