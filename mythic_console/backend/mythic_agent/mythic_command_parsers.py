from cmd2 import Cmd2ArgumentParser

##### User Parsers #####

user_parser = Cmd2ArgumentParser()
user_subparsers = user_parser.add_subparsers(title='subcommands', help='subcommand help')

user_create_parser = user_subparsers.add_parser('create', help='create a user')
user_create_parser.add_argument('username', help='username of user')
user_create_parser.add_argument('password', help='password of user')

user_list_parser = user_subparsers.add_parser('list', help='list users')
user_list_parser.add_argument('--all', action='store_true', help='include deleted users')

user_info_parser = user_subparsers.add_parser('info', help='show details for one user')
user_info_parser.add_argument('identifier', help='user id or username')

user_set_parser = user_subparsers.add_parser('set', help='change a user field')
user_set_subparsers = user_set_parser.add_subparsers(title='field', help='field help')

user_set_admin_parser = user_set_subparsers.add_parser('admin', help='grant or revoke admin')
user_set_admin_parser.add_argument('value', choices=['true', 'false'],
                                    help='true to grant admin, false to revoke')
user_set_admin_parser.add_argument('identifier', help='user id or username')
user_set_admin_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

user_set_active_parser = user_set_subparsers.add_parser('active', help='enable or disable an account')
user_set_active_parser.add_argument('value', choices=['true', 'false'],
                                     help='true to enable, false to disable')
user_set_active_parser.add_argument('identifier', help='user id or username')
user_set_active_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

user_delete_parser = user_subparsers.add_parser('delete', help='soft-delete a user')
user_delete_parser.add_argument('identifier', help='user id or username')
user_delete_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

##### Operation Parsers #####

operation_parser = Cmd2ArgumentParser()
operation_subparsers = operation_parser.add_subparsers(title='subcommands', help='subcommand help')

operation_list_parser = operation_subparsers.add_parser('list', help='list operations')
operation_list_parser.add_argument('-v', '--verbose', action='store_true',
                                    help='show all columns and include deleted operations')

operation_info_parser = operation_subparsers.add_parser('info', help='show details for one operation')
operation_info_parser.add_argument('operation', help='operation id or name')

operation_set_parser = operation_subparsers.add_parser('set', help='switch the active operation')
operation_set_parser.add_argument('operation', help='operation id or name')

operation_create_parser = operation_subparsers.add_parser('create', help='create an operation')
operation_create_parser.add_argument('name', help='name of operation')
operation_create_parser.add_argument('--lead', default=None, help='username to set as operation lead')

operation_update_parser = operation_subparsers.add_parser('update', help='update an operation')
operation_update_parser.add_argument('operation', help='operation id or name')
operation_update_parser.add_argument('--name', default=None, help='new operation name')
operation_update_parser.add_argument('--channel', default=None, help='new notification channel')
operation_update_parser.add_argument('--webhook', default=None, help='new webhook url')
operation_update_parser.add_argument('--lead', default=None, help='username to set as operation lead')
operation_update_complete_group = operation_update_parser.add_mutually_exclusive_group()
operation_update_complete_group.add_argument('--complete', action='store_true', help='mark operation complete')
operation_update_complete_group.add_argument('--incomplete', action='store_true',
                                              help='mark operation incomplete')
operation_update_delete_group = operation_update_parser.add_mutually_exclusive_group()
operation_update_delete_group.add_argument('--delete', action='store_true', help='soft-delete operation')
operation_update_delete_group.add_argument('--restore', action='store_true', help='restore a deleted operation')
operation_update_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_operator_parser = operation_subparsers.add_parser('operator', help='manage operation members')
operation_operator_subparsers = operation_operator_parser.add_subparsers(title='subcommands', help='subcommand help')

operation_operator_add_parser = operation_operator_subparsers.add_parser('add', help='add a member to an operation')
operation_operator_add_parser.add_argument('operation', help='operation id or name')
operation_operator_add_parser.add_argument('username', help='username to add')

operation_operator_remove_parser = operation_operator_subparsers.add_parser(
    'remove', help='remove a member from an operation')
operation_operator_remove_parser.add_argument('operation', help='operation id or name')
operation_operator_remove_parser.add_argument('username', help='username to remove')
operation_operator_remove_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_operator_role_parser = operation_operator_subparsers.add_parser(
    'role', help='change a member\'s role')
operation_operator_role_parser.add_argument('operation', help='operation id or name')
operation_operator_role_parser.add_argument('username', help='username to update')
operation_operator_role_parser.add_argument('--role', choices=['operator', 'spectator'], default='operator',
                                             help='role to assign')

operation_blocklist_parser = operation_subparsers.add_parser(
    'blocklist', help='manage command block lists for the active operation')
operation_blocklist_subparsers = operation_blocklist_parser.add_subparsers(
    title='subcommands', help='subcommand help')

operation_blocklist_list_parser = operation_blocklist_subparsers.add_parser('list', help='list block lists')

operation_blocklist_show_parser = operation_blocklist_subparsers.add_parser('show', help='show a block list')
operation_blocklist_show_parser.add_argument('name', help='block list name')

operation_blocklist_create_parser = operation_blocklist_subparsers.add_parser(
    'create', help='create a block list seeded with one or more commands')
operation_blocklist_create_parser.add_argument('name', help='block list name')
operation_blocklist_create_parser.add_argument('command', nargs='+', help='command name(s) to block')
operation_blocklist_create_parser.add_argument('--payload-type', default=None,
                                                help='payload type to disambiguate the command name')

operation_blocklist_add_parser = operation_blocklist_subparsers.add_parser(
    'add', help='add a command to a block list (creates it if absent)')
operation_blocklist_add_parser.add_argument('name', help='block list name')
operation_blocklist_add_parser.add_argument('command', help='command name to block')
operation_blocklist_add_parser.add_argument('--payload-type', default=None,
                                             help='payload type to disambiguate the command name')

operation_blocklist_remove_parser = operation_blocklist_subparsers.add_parser(
    'remove', help='remove a command from a block list')
operation_blocklist_remove_parser.add_argument('name', help='block list name')
operation_blocklist_remove_parser.add_argument('command', help='command name to unblock')
operation_blocklist_remove_parser.add_argument('--payload-type', default=None,
                                                help='payload type to disambiguate the command name')
operation_blocklist_remove_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_blocklist_assign_parser = operation_blocklist_subparsers.add_parser(
    'assign', help='assign a block list to one or more operators')
operation_blocklist_assign_parser.add_argument('name', help='block list name')
operation_blocklist_assign_parser.add_argument('operator', nargs='+', help='operator username(s)')
operation_blocklist_assign_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_blocklist_unassign_parser = operation_blocklist_subparsers.add_parser(
    'unassign', help='unassign a block list from one or more operators')
operation_blocklist_unassign_parser.add_argument('name', help='block list name')
operation_blocklist_unassign_parser.add_argument('operator', nargs='+', help='operator username(s)')
operation_blocklist_unassign_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_blocklist_delete_parser = operation_blocklist_subparsers.add_parser(
    'delete', help='delete a block list')
operation_blocklist_delete_parser.add_argument('name', help='block list name')
operation_blocklist_delete_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

##### Operation Whitelist Parsers #####

_whitelist_help = (
    'manage command block lists for the active operation by naming the commands to allow. '
    'This creates and edits an ordinary block list holding the complement of the allowed commands. '
    'The complement is a point-in-time snapshot: commands added to a payload type later are not '
    'auto-blocked until the whitelist is recreated. `show`/`list` display the stored block list '
    '(the complement of the allowed commands), not the allowed set.'
)

operation_whitelist_parser = operation_subparsers.add_parser(
    'whitelist', help=_whitelist_help, description=_whitelist_help)
operation_whitelist_subparsers = operation_whitelist_parser.add_subparsers(
    title='subcommands', help='subcommand help')

operation_whitelist_list_parser = operation_whitelist_subparsers.add_parser('list', help='list block lists')

operation_whitelist_show_parser = operation_whitelist_subparsers.add_parser(
    'show', help='show a block list (the stored block list, not the allowed set)')
operation_whitelist_show_parser.add_argument('name', help='block list name')

operation_whitelist_create_parser = operation_whitelist_subparsers.add_parser(
    'create',
    help='create a block list allowing only the given command(s); blocks everything else',
    description=_whitelist_help)
operation_whitelist_create_parser.add_argument('name', help='block list name')
operation_whitelist_create_parser.add_argument('command', nargs='+', help='command name(s) to allow')
operation_whitelist_create_parser.add_argument('--payload-type', default=None,
                                                help='payload type to scope the allowed command(s) to')

operation_whitelist_add_parser = operation_whitelist_subparsers.add_parser(
    'add', help='allow a command (removes it from the underlying block list)')
operation_whitelist_add_parser.add_argument('name', help='block list name')
operation_whitelist_add_parser.add_argument('command', help='command name to allow')
operation_whitelist_add_parser.add_argument('--payload-type', default=None,
                                             help='payload type to disambiguate the command name')

operation_whitelist_remove_parser = operation_whitelist_subparsers.add_parser(
    'remove', help='stop allowing a command (adds it to the underlying block list)')
operation_whitelist_remove_parser.add_argument('name', help='block list name')
operation_whitelist_remove_parser.add_argument('command', help='command name to stop allowing')
operation_whitelist_remove_parser.add_argument('--payload-type', default=None,
                                                help='payload type to disambiguate the command name')
operation_whitelist_remove_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_whitelist_assign_parser = operation_whitelist_subparsers.add_parser(
    'assign', help='assign a whitelist to one or more operators')
operation_whitelist_assign_parser.add_argument('name', help='block list name')
operation_whitelist_assign_parser.add_argument('operator', nargs='+', help='operator username(s)')
operation_whitelist_assign_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_whitelist_unassign_parser = operation_whitelist_subparsers.add_parser(
    'unassign', help='unassign a whitelist from one or more operators')
operation_whitelist_unassign_parser.add_argument('name', help='block list name')
operation_whitelist_unassign_parser.add_argument('operator', nargs='+', help='operator username(s)')
operation_whitelist_unassign_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

operation_whitelist_delete_parser = operation_whitelist_subparsers.add_parser(
    'delete', help='delete a whitelist')
operation_whitelist_delete_parser.add_argument('name', help='block list name')
operation_whitelist_delete_parser.add_argument('--force', action='store_true', help='skip confirmation prompt')

##### Payload Parsers #####

payload_parser = Cmd2ArgumentParser()
payload_subparsers = payload_parser.add_subparsers(title='subcommands', help='subcommand help')

payload_list_parser = payload_subparsers.add_parser('list', help='list payloads')

payload_download_parser = payload_subparsers.add_parser('download', help='download a payload')
payload_download_parser.add_argument("id", type=int, help="payload id to download")
payload_download_parser.add_argument("path", nargs="+", help="local path to save payload to")

payload_build_parser = payload_subparsers.add_parser('build', help='build and download a payload from a JSON config')
payload_build_parser.add_argument("payload_type", help="payload type to build (see `payload list`/server catalog)")
payload_build_parser.add_argument("-o", "--output", default=None,
                                   help="local path to save the built payload (default: temp file)")
payload_build_parser.add_argument("--config", default=None,
                                   help="JSON build config: a file path or a JSON string")

payload_types_parser = payload_subparsers.add_parser('types', help='list payload types available on the server')

##### C2 Profile Parsers #####

profiles_parser = Cmd2ArgumentParser()
profiles_subparsers = profiles_parser.add_subparsers(title='subcommands', help='subcommand help')

profiles_list_parser = profiles_subparsers.add_parser('list', help='list c2 profiles')

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
