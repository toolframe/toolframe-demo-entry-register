"""Require a release tag that exactly matches the checked-out project version."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def main() -> None:
    project = Path(__file__).resolve().parents[1] / "pyproject.toml"
    version = tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"]
    expected = f"refs/tags/v{version}"
    if len(sys.argv) != 2 or sys.argv[1] != expected:
        raise SystemExit(
            f"Publishing requires {expected}; select that tag when dispatching."
        )
    print(f"Release tag matches project.version: v{version}")


if __name__ == "__main__":
    main()
