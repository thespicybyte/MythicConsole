import argparse

from utils.environment import Environment
from .installer import PluginInstallError, install, list_installed, remove
from .scaffold import ScaffoldError, scaffold
from .validate import validate_plugin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="console.py")
    subparsers = parser.add_subparsers(dest="action")

    install_parser = subparsers.add_parser("install", help="install a plugin from a GitHub URL or local path")
    install_parser.add_argument("source", help="GitHub URL or local folder path")
    install_parser.add_argument("--branch", default=None, help="git branch to clone (GitHub source only)")
    install_parser.add_argument("--subdir", default=None,
                                help="subdirectory within the repo holding the plugin (GitHub source only)")

    plugin_parser = subparsers.add_parser("plugin", help="manage installed plugins")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_action")
    plugin_subparsers.add_parser("list", help="list installed plugins")
    remove_parser = plugin_subparsers.add_parser("remove", help="remove an installed plugin")
    remove_parser.add_argument("name", help="plugin name to remove")

    new_parser = plugin_subparsers.add_parser("new", help="scaffold a new plugin")
    new_parser.add_argument("name", help="plugin/package name")
    new_parser.add_argument("payload_type", help="Mythic payload type this plugin handles")
    new_parser.add_argument("--author", default="", help="plugin author")
    new_parser.add_argument("--description", default="", help="plugin description")
    new_parser.add_argument("--dir", default=".", help="parent directory to create the plugin in")

    validate_parser = plugin_subparsers.add_parser("validate", help="validate a plugin before shipping it")
    validate_parser.add_argument("path", help="path to the plugin directory")

    return parser


def run(argv) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    plugins_dir = Environment().plugins_directory()

    if args.action == "install":
        try:
            manifest = install(args.source, plugins_dir, branch=args.branch, subdir=args.subdir)
        except PluginInstallError as e:
            print(f"[-] install failed: {e}")
            return 1
        print(f"[+] installed '{manifest.name}' (payload type: {manifest.payload_type})")
        return 0

    if args.action == "plugin":
        if args.plugin_action == "list":
            manifests = list_installed(plugins_dir)
            if not manifests:
                print("no plugins installed")
                return 0
            for manifest in manifests:
                print(f"{manifest.name}\t{manifest.payload_type}\t{manifest.version}")
            return 0

        if args.plugin_action == "remove":
            try:
                remove(args.name, plugins_dir)
            except PluginInstallError as e:
                print(f"[-] remove failed: {e}")
                return 1
            print(f"[+] removed '{args.name}'")
            return 0

        if args.plugin_action == "new":
            try:
                path = scaffold(args.name, args.payload_type, author=args.author,
                                description=args.description, parent=args.dir)
            except ScaffoldError as e:
                print(f"[-] scaffold failed: {e}")
                return 1
            print(f"[+] created plugin '{args.name}' at {path}")
            print(f"    next: python console.py install {path}")
            return 0

        if args.plugin_action == "validate":
            errors, advisories = validate_plugin(args.path)
            for advisory in advisories:
                print(f"[!] {advisory}")
            for error in errors:
                print(f"[-] {error}")
            if errors:
                return 1
            print(f"[+] '{args.path}' looks valid")
            return 0

        print("plugin: expected 'list', 'remove', 'new', or 'validate'")
        return 2

    print("expected 'install' or 'plugin'")
    return 2
