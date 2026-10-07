#!/usr/bin/env python3
"""Source-checkout entry point. The installed command is ``hand-mouse``."""

import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from hand_mouse.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
