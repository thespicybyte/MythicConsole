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
