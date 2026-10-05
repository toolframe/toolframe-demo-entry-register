"""Run CI in temporary copies, keeping local sibling checkouts read-only."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

DEPENDENCIES = {
    "toolframe-sdk": "379217bc5210b7ecc3dda5a6937f4fad3b6baa00",
    "toolframe-storage-sqlite": "6854818147a9f13e180a4cfbe70d6a9bce077069",
}


def run(*args: str | Path, cwd: Path, env: dict[str, str]) -> None:
    command = [str(arg) for arg in args]
    print(f"+ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def snapshot(source: Path, destination: Path) -> None:
    """Include current tracked and unignored edits, without copying local build state."""
    paths = subprocess.check_output(
        [
            "git",
            "-C",
            str(source),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ]
    )
    for item in set(paths.split(b"\0")) - {b""}:
        relative = Path(os.fsdecode(item))
        original = source / relative
        if original.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)


def export_dependency(
    source: Path, destination: Path, revision: str, work: Path
) -> None:
    archive = work / f"{destination.name}.tar"
    with archive.open("wb") as stream:
        subprocess.run(
            ["git", "-C", str(source), "archive", "--format=tar", revision],
            stdout=stream,
            check=True,
        )
    destination.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    archive.unlink()
    print(f"Pinned dependency: {destination.name}@{revision}", flush=True)


def validate(source: Path, siblings: Path, work: Path, output: Path) -> None:
    project = work / source.name
    snapshot(source, project)
    for name, revision in DEPENDENCIES.items():
        export_dependency(siblings / name, work / name, revision, work)

    env = os.environ.copy()
    for name in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    env.update(
        UV_PYTHON=sys.executable,
        UV_PROJECT_ENVIRONMENT=str(work / "test-env"),
        UV_CACHE_DIR=env.get("UV_CACHE_DIR", str(work / "uv-cache")),
        UV_NO_PROGRESS="1",
        PYTHONNOUSERSITE="1",
    )

    def call(*args: str | Path, cwd: Path = project) -> None:
        run(*args, cwd=cwd, env=env)

    call("uv", "sync", "--locked", "--dev", "--extra", "ui")
    test_python = work / "test-env/bin/python"
    call(test_python, "-m", "ruff", "check", ".")
    call(test_python, "-m", "pytest", "-q")

    wheels = work / "dependency-wheels"
    for name in DEPENDENCIES:
        call("uv", "build", "--no-sources", "--wheel", work / name, "--out-dir", wheels)
    dist = work / "dist"
    call("uv", "build", "--no-sources", "--out-dir", dist)
    (wheel,) = dist.glob("*.whl")
    (sdist,) = dist.glob("*.tar.gz")
    (sdk_wheel,) = wheels.glob("toolframe_sdk-*.whl")
    (storage_wheel,) = wheels.glob("toolframe_storage_sqlite-*.whl")

    call("uv", "venv", work / "metadata-env")
    metadata_python = work / "metadata-env/bin/python"
    call("uv", "pip", "install", "--python", metadata_python, "twine==7.0.0")
    call(metadata_python, "-m", "twine", "check", "--strict", wheel, sdist)

    call("uv", "venv", work / "wheel-env")
    wheel_python = work / "wheel-env/bin/python"
    wheel_run = work / "wheel-run"
    wheel_run.mkdir()
    # Explicit wheel inputs ensure the pinned SDK is used, with its real dependencies.
    call(
        "uv",
        "pip",
        "install",
        "--python",
        wheel_python,
        wheel,
        sdk_wheel,
        cwd=wheel_run,
    )
    call("uv", "pip", "check", "--python", wheel_python, cwd=wheel_run)
    call(
        wheel_python,
        "-I",
        project / "scripts/verify_wheel.py",
        project,
        dist,
        cwd=wheel_run,
    )

    # Exercise the installed wheel's page and storage integration as well as source tests.
    lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
    test_tools = [
        f"{package['name']}=={package['version']}"
        for package in lock["package"]
        if package["name"] in {"pytest", "pytest-asyncio"}
    ]
    call(
        "uv",
        "pip",
        "install",
        "--python",
        wheel_python,
        f"{wheel}[ui]",
        sdk_wheel,
        storage_wheel,
        *test_tools,
        cwd=wheel_run,
    )
    call("uv", "pip", "check", "--python", wheel_python, cwd=wheel_run)
    installed_tests = work / "installed-tests"
    shutil.copytree(
        project / "tests", installed_tests, ignore=shutil.ignore_patterns("__pycache__")
    )
    call(
        wheel_python,
        "-I",
        "-m",
        "pytest",
        "-q",
        "--import-mode=importlib",
        "-c",
        project / "pyproject.toml",
        installed_tests,
        cwd=wheel_run,
    )

    output.mkdir(parents=True, exist_ok=True)
    for artifact in (wheel, sdist):
        shutil.copy2(artifact, output / artifact.name)
    print(f"Validated distributions: {output}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="New or empty artifact directory"
    )
    parser.add_argument(
        "--siblings",
        type=Path,
        help="Parent directory containing sibling Git repositories",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep temporary environments for inspection",
    )
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("Run this command with Python 3.14 (CI uses 3.14.7).")
    source = Path(__file__).resolve().parents[1]
    output = args.output_dir.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error(
            "--output-dir must be absent or empty; existing artifacts are never reused."
        )
    work = Path(tempfile.mkdtemp(prefix="entry-register-ci-"))
    print(f"Isolated workspace: {work}", flush=True)
    try:
        validate(source, (args.siblings or source.parent).resolve(), work, output)
    finally:
        if args.keep_workdir:
            print(f"Kept isolated workspace: {work}", flush=True)
        else:
            shutil.rmtree(work)


if __name__ == "__main__":
    main()
