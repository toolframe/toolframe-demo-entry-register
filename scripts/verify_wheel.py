"""Verify a headless installation and packaged assets from the built distributions."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
import sys
import tarfile
import tomllib
import zipfile
from importlib.resources import files
from pathlib import Path


def main() -> None:
    source, dist = (Path(value) for value in sys.argv[1:])
    project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    name = "toolframe_demo_entry_register"
    distribution = importlib.metadata.distribution(project["name"])
    assert distribution.version == project["version"]
    assert distribution.metadata["License-Expression"] == "MIT"
    assert distribution.metadata.get_all("License-File") == ["LICENSE"]
    assert set(project["dependencies"]).issubset(distribution.requires)
    assert importlib.util.find_spec("streamlit") is None, (
        "The base wheel must remain headless"
    )
    assert importlib.util.find_spec("toolframe_storage_sqlite") is None
    assert importlib.util.find_spec("opentelemetry") is None

    import toolframe_sdk

    import toolframe_demo_entry_register
    import toolframe_demo_entry_register.page
    from toolframe_demo_entry_register.service import EntryRegister

    context = toolframe_sdk.RuntimeContext(
        None, plugin_id="entry-register", generation="wheel-smoke"
    )
    assert isinstance(EntryRegister(context).log, logging.LoggerAdapter)

    for module in (toolframe_demo_entry_register, toolframe_sdk):
        assert (
            Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
        )
    (entry_point,) = (
        entry
        for entry in distribution.entry_points
        if entry.group == "toolframe.plugins" and entry.name == "entry-register"
    )
    plugin = entry_point.load()
    assert plugin.id == "entry-register"
    assert plugin.store.revision == "v1"
    assert plugin.services["entry-register.entries"].methods["list_entries"].read_only
    assert (
        plugin.services["entry-register.entries"].methods["list_entries_tool"].read_only
    )

    assets = (
        "migrations/0001_init.sql",
        "docs/usage.md",
        "templates/entry-register.toml",
    )
    (wheel,) = dist.glob("*.whl")
    (sdist,) = dist.glob("*.tar.gz")
    with zipfile.ZipFile(wheel) as bundle:
        for asset in assets:
            expected = (source / "src" / name / asset).read_bytes()
            assert bundle.read(f"{name}/{asset}") == expected
            assert files(name).joinpath(asset).read_bytes() == expected
        (license_path,) = (
            path
            for path in bundle.namelist()
            if path.endswith(".dist-info/licenses/LICENSE")
        )
        assert bundle.read(license_path) == (source / "LICENSE").read_bytes()
        assert (
            distribution.locate_file(license_path).read_bytes()
            == (source / "LICENSE").read_bytes()
        )

    with tarfile.open(sdist) as bundle:
        root = f"{name}-{project['version']}"
        for asset in (
            "LICENSE",
            "examples/toolframe.toml",
            *(f"src/{name}/{item}" for item in assets),
        ):
            member = bundle.extractfile(f"{root}/{asset}")
            assert member is not None, asset
            assert member.read() == (source / asset).read_bytes()
    print(
        "PASS: installed wheel imports from its clean environment with runtime dependencies"
    )
    print(
        "PASS: headless entry point, read-only tools, MIT license, migration, docs and templates"
    )


if __name__ == "__main__":
    main()
