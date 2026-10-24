from poseidon.formatter import PoseidonFormatter


def test_poseidon_registry_contents():
    assert PoseidonFormatter._renderers == {
        "ls": "ls",
        "download": "download",
        "drives": "drives",
        "getenv": "get_env",
        "jobs": "jobs",
        "portscan": "portscan",
        "ps": "ps",
        "sshauth": "ssh_auth",
        "config": "config",
        "getuser": "user_info",
        "keys": "user_info",
    }


def test_execute_library_is_not_registered():
    assert "execute_library" not in PoseidonFormatter._renderers


def test_multi_name_renderer_shares_one_method():
    assert PoseidonFormatter._renderers["getuser"] == PoseidonFormatter._renderers["keys"]
