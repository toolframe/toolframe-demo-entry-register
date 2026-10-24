# CI and publishing

## Local validation

Use Git, uv 0.12.8, Python 3.14.7, and internet access to PyPI. Keep the sibling
Git repositories below next to this repository, or pass their parent directory
with `--siblings /path/to/workspace`.

| Repository | Required commit |
| --- | --- |
| `toolframe-sdk` | `539ced4dbdf9e303ec0f0205a35d65287a480b2a` |
| `toolframe-sql-sqlite` | `d4f3fcf9d8145fd0dab3d57aad8a452fb5aa527b` |

Run from the repository root:

```shell
artifacts=$(mktemp -d)
uv run --isolated --no-project --python 3.14.7 python scripts/ci.py \
  --output-dir "$artifacts/dist" --keep-workdir
```

This is the same validation script used by GitHub Actions. It copies the current
tracked and unignored working files to a temporary workspace, exports the exact
sibling commits with `git archive`, and creates a fresh uv cache and separate
environments. Sibling working trees, existing `.venv` directories, `uv.lock`,
and existing `dist` directories are never updated or reused. The output directory
must be new or empty; only successfully validated distributions are copied there.
Omit `--keep-workdir` to remove the temporary workspace on exit.

If downloads are constrained, set `UV_CACHE_DIR` to an existing uv download cache.
This optional cache reuse does not reuse virtual environments, distribution
artifacts, or the sibling wheelhouse: those are always created afresh.

The script runs:

1. `uv sync --locked --dev --extra ui`, Ruff, and the complete pytest suite,
   including plugin/storage integration and Streamlit page tests.
2. New dependency wheels from the pinned SDK and SQLite sources, followed by
   `uv build --no-sources` for this package's sdist and wheel.
3. `twine check --strict` using Twine 7.0.0 in a separate tools environment.
4. A fresh wheel installation with the pinned SDK wheel and its real runtime
   dependencies, followed by `uv pip check`. An isolated Python process checks
   imports, the plugin entry point, read-only MCP methods, the MIT license, and
   byte-identical migration, usage document, and composition template assets.
   It also verifies that the base installation contains neither Streamlit nor
   the SQLite provider. The sdist must retain the license and example template.
5. Installation of the wheel's `ui` extra and the SQLite wheel, another dependency
   check, and the full pytest suite against the installed wheel. Tests are copied
   outside the source tree and run from an empty working directory with isolated
   Python and importlib imports.

The source test environment uses `uv.lock`. The wheel installation deliberately
resolves runtime dependencies from the distribution metadata and PyPI, with the
pinned unpublished Toolframe wheels supplied directly. It never uses `--no-deps`.

The release guard can also be checked locally without creating a tag:

```shell
uv run --isolated --no-project --python 3.14.7 python scripts/check_release.py refs/tags/v0.4.1
```

Run `actionlint` (locally verified with 1.7.12) from this repository to validate
both workflows and their inline shell commands. There are no standalone shell
scripts. `python scripts/ci.py --help` describes the script options.

## GitHub Actions

`ci.yml` runs on pushes to `main`, pull requests, manual dispatches, and reusable
workflow calls. It uses Ubuntu 24.04, Python 3.14.7, uv 0.12.8, read-only repository
permissions, and a 20-minute timeout. Successful runs retain the wheel and sdist
as `python-dists-<github.sha>` for seven days. This verifies the Python plugin;
it does not establish support for the complete Toolframe application on Linux.

Actions are pinned to full commit IDs. Dependency checkouts use the commits
listed above. Their owner defaults to `github.repository_owner`, which is the
base repository owner on pull requests. Set the repository variable
`TOOLFRAME_REPOSITORY_OWNER` if the dependencies belong to a different owner.
No dependency checkout follows a fork contributor's owner or a moving branch.
The sibling repositories and these exact commits must be available on GitHub
under the selected owner. The supplied workflow expects public sibling
repositories; the default `GITHUB_TOKEN` cannot read unrelated private ones.

`publish.yml` is manual only. Choose `testpypi` (the default) or `pypi` and run it
against a tag exactly matching `v<project.version>`; the current version requires
`v0.4.1`. A branch dispatch or mismatched tag fails before validation or upload.
The workflow reuses `ci.yml` at the same revision, then downloads that run's
validated distributions. It never rebuilds in the publishing job. CI has no
concurrency group, so it cannot cancel the calling publish workflow. Publishing
uses its own non-cancelling concurrency group per tag and index.

## Publication

See [releasing](releasing.md) for dependency order, private repository access,
Trusted Publisher bindings, version tags and consumer installation checks.

## Local verification scope

Local execution is on macOS arm64 with Python 3.14.7. The recorded results cover
fresh environments, source and installed-wheel tests, metadata and packaged
asset checks, plus static workflow validation. They are not evidence of an
executed GitHub-hosted Ubuntu run or a successful OIDC publication. This plugin
validation does not cover other providers in the composition template or the
full Toolframe launcher.

The first page render has a bounded 60-second timeout for cold native-library
imports. Later interactions retain their normal limits; tests do not use retries
or skip assertions.
