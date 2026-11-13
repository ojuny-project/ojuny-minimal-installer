#!/usr/bin/env python3
"""Reject fixed template paths in the installer.

The module contract in ojuny-template/docs/12-flake-module-contract.md is the
only way to find a template file. flake_structure.py is the vendored
implementation and is exempt.
"""

import argparse
import sys
from pathlib import Path

FORBIDDEN = ("modules/07-system", "modules/01-users", "modules/backend", "12-multiboot.nix")
EXEMPT = {"flake_structure.py"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    arguments = parser.parse_args()
    root = Path(arguments.root).resolve()
    targets = [
        path
        for path in (root / "installer").rglob("*")
        if path.is_file() and path.suffix in (".py", ".nix") and path.name not in EXEMPT
    ]

    failures = []
    for path in targets:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for value in FORBIDDEN:
                if value in line:
                    failures.append("{}:{}: {}".format(path.relative_to(root), number, value))

    if failures:
        print(
            "Fixed template paths are not allowed. Use the module contract in "
            "ojuny-template/docs/12-flake-module-contract.md.",
            file=sys.stderr,
        )
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("fixed-paths: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
