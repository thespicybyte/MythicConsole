# Releasing

## Automated release (PyPI trusted publishing)

1. Bump `__version__` in `mythic_console/version.py`.
2. Commit the bump, then tag it and push the tag:
   ```shell
   git tag v<version>
   git push origin v<version>
   ```
3. Pushing a tag matching `v*` triggers `.github/workflows/publish.yml`, which builds the sdist
   and wheel and publishes them to PyPI via
   [trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — no stored token or
   secret is needed in the repo.

Trusted publishing requires a one-time setup on PyPI: register this repository and the
`publish.yml` workflow as a trusted publisher for the `mythic-console` project, with the GitHub
Actions environment named `pypi` (matching the `environment: pypi` in the workflow). This is done
once by whoever owns the PyPI project.

## Manual release (TestPyPI dry run, or a token-based fallback)

Build locally:

```shell
python -m pip install --upgrade build twine
python -m build
```

This produces `dist/mythic_console-<version>-py3-none-any.whl` and a matching sdist.

Dry run against TestPyPI first:

```shell
twine upload --repository testpypi dist/*
pipx install --index-url https://test.pypi.org/simple/ \
  --pip-args="--extra-index-url https://pypi.org/simple/" mythic-console
```

The extra index is required because `mythic-console`'s dependencies live on the real PyPI, not
TestPyPI.

Token-based fallback to the real PyPI (only if trusted publishing is unavailable):

```shell
twine upload dist/*
```

This prompts for (or reads from `TWINE_USERNAME`/`TWINE_PASSWORD` or a `~/.pypirc` entry) a PyPI
API token scoped to the `mythic-console` project.

## Verifying a build without uploading

```shell
python -m build
python -m venv /tmp/mc-verify && /tmp/mc-verify/bin/pip install dist/mythic_console-*.whl
/tmp/mc-verify/bin/mythic-console            # should launch with a styled TUI
/tmp/mc-verify/bin/mythic-console plugin list
```

A styled launch confirms `mythic.tcss` shipped inside the wheel and is being loaded from
`site-packages`, not a source checkout.
