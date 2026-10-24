import json

import pytest

from plugins.manifest import InvalidManifest, load_manifest

VALID = {
    "schema_version": 1,
    "name": "sample",
    "payload_type": "sample",
    "entrypoint": "sample:Sample",
    "version": "1.0.0",
}


def _write_manifest(tmp_path, data):
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    return tmp_path


def test_load_manifest_valid(tmp_path):
    manifest = load_manifest(_write_manifest(tmp_path, VALID))

    assert manifest.name == "sample"
    assert manifest.payload_type == "sample"
    assert manifest.entrypoint_module == "sample"
    assert manifest.entrypoint_class == "Sample"


def test_load_manifest_accepts_file_path_directly(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(VALID))

    manifest = load_manifest(manifest_path)

    assert manifest.name == "sample"


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(InvalidManifest):
        load_manifest(tmp_path)


def test_load_manifest_invalid_json(tmp_path):
    (tmp_path / "manifest.json").write_text("{not json")

    with pytest.raises(InvalidManifest):
        load_manifest(tmp_path)


@pytest.mark.parametrize("field", ["name", "payload_type", "entrypoint", "version"])
def test_load_manifest_missing_required_field(tmp_path, field):
    data = dict(VALID)
    del data[field]

    with pytest.raises(InvalidManifest):
        load_manifest(_write_manifest(tmp_path, data))


def test_load_manifest_missing_schema_version(tmp_path):
    data = dict(VALID)
    del data["schema_version"]

    with pytest.raises(InvalidManifest):
        load_manifest(_write_manifest(tmp_path, data))


def test_load_manifest_unknown_schema_version(tmp_path):
    data = dict(VALID, schema_version=99)

    with pytest.raises(InvalidManifest):
        load_manifest(_write_manifest(tmp_path, data))


@pytest.mark.parametrize("bad_name", ["has space", "has-dash", "1starts_with_digit", ""])
def test_load_manifest_invalid_name(tmp_path, bad_name):
    data = dict(VALID, name=bad_name)

    with pytest.raises(InvalidManifest):
        load_manifest(_write_manifest(tmp_path, data))


@pytest.mark.parametrize("bad_entrypoint", ["sample", "sample:Sample:Extra", ":Sample", "sample:"])
def test_load_manifest_invalid_entrypoint_shape(tmp_path, bad_entrypoint):
    data = dict(VALID, entrypoint=bad_entrypoint)

    with pytest.raises(InvalidManifest):
        load_manifest(_write_manifest(tmp_path, data))


def test_load_manifest_optional_fields_default_empty(tmp_path):
    manifest = load_manifest(_write_manifest(tmp_path, VALID))

    assert manifest.author == ""
    assert manifest.description == ""


def test_load_manifest_optional_fields_preserved(tmp_path):
    data = dict(VALID, author="me", description="a sample plugin")

    manifest = load_manifest(_write_manifest(tmp_path, data))

    assert manifest.author == "me"
    assert manifest.description == "a sample plugin"
