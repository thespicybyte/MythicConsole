from cmd2 import Cmd2ArgumentParser

##### User Parsers #####

user_parser = Cmd2ArgumentParser()
user_subparsers = user_parser.add_subparsers(title='subcommands', help='subcommand help')

user_create_parser = user_subparsers.add_parser('create', help='create a user')
user_create_parser.add_argument('username', help='username of user')
user_create_parser.add_argument('password', help='password of user')

user_list_parser = user_subparsers.add_parser('list', help='list users')

##### Operation Parsers #####

operation_parser = Cmd2ArgumentParser()
operation_subparsers = operation_parser.add_subparsers(title='subcommands', help='subcommand help')

operation_list_parser = operation_subparsers.add_parser('list', help='list operations')

##### Payload Parsers #####

payload_parser = Cmd2ArgumentParser()
payload_subparsers = payload_parser.add_subparsers(title='subcommands', help='subcommand help')

payload_list_parser = payload_subparsers.add_parser('list', help='list payloads')

payload_download_parser = payload_subparsers.add_parser('download', help='download a payload')
payload_download_parser.add_argument("id", type=int, help="payload id to download")
payload_download_parser.add_argument("path", nargs="+", help="local path to save payload to")

##### Callback Parsers #####

callback_parser = Cmd2ArgumentParser()
callback_subparsers = callback_parser.add_subparsers(title='subcommands', help='subcommand help')

callback_export_parser = callback_subparsers.add_parser('export', help='export a callback config to a file')
callback_export_parser.add_argument("id", type=int, help="callback id to export")
callback_export_parser.add_argument("path", nargs="*",
                                    help="local path to save config to "
                                         "(default: DOWNLOAD_DIRECTORY/callback_<id>_export.json)")

callback_import_parser = callback_subparsers.add_parser('import', help='import a callback config from a file')
callback_import_parser.add_argument("path", nargs="+", help="local path to the config file to import")
