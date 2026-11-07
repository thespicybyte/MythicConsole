import json
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

_REQUIRED_FIELDS = ("schema_version", "name", "payload_type", "entrypoint", "version")


class InvalidManifest(Exception):
    pass


@dataclass
class PluginManifest:
    schema_version: int
    name: str
    payload_type: str
    entrypoint: str
    version: str
    author: str = ""
    description: str = ""

    @property
    def entrypoint_module(self) -> str:
        return self.entrypoint.split(":", 1)[0]

    @property
    def entrypoint_class(self) -> str:
        return self.entrypoint.split(":", 1)[1]


def _validate(data: dict, source: str) -> None:
    for field in _REQUIRED_FIELDS:
        if not data.get(field) and field != "schema_version":
            raise InvalidManifest(f"{source}: missing required field '{field}'")

    if "schema_version" not in data:
        raise InvalidManifest(f"{source}: missing required field 'schema_version'")

    if data["schema_version"] != SCHEMA_VERSION:
        raise InvalidManifest(
            f"{source}: unsupported schema_version {data['schema_version']!r} "
            f"(this console supports {SCHEMA_VERSION})")

    name = data["name"]
    if not isinstance(name, str) or not name.isidentifier():
        raise InvalidManifest(f"{source}: 'name' must be a valid Python identifier, got {name!r}")

    entrypoint = data["entrypoint"]
    if not isinstance(entrypoint, str) or entrypoint.count(":") != 1:
        raise InvalidManifest(
            f"{source}: 'entrypoint' must be '<module>:<Class>', got {entrypoint!r}")
    module, _, cls_name = entrypoint.partition(":")
    if not module or not cls_name:
        raise InvalidManifest(
            f"{source}: 'entrypoint' must be '<module>:<Class>', got {entrypoint!r}")


def load_manifest(path: Path) -> PluginManifest:
    """Load and validate a plugin's manifest.json at `path` (the plugin directory or the file itself)."""
    manifest_path = path if path.name == "manifest.json" else path / "manifest.json"

    if not manifest_path.is_file():
        raise InvalidManifest(f"{manifest_path}: manifest.json not found")

    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        raise InvalidManifest(f"{manifest_path}: invalid JSON: {e}")

    _validate(data, str(manifest_path))

    return PluginManifest(
        schema_version=data["schema_version"],
        name=data["name"],
        payload_type=data["payload_type"],
        entrypoint=data["entrypoint"],
        version=data["version"],
        author=data.get("author", ""),
        description=data.get("description", ""),
    )
