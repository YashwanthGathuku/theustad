#!/usr/bin/env python3
"""Deprecated Gate entry point forwarding to TheUstad."""

import sys

from theustad import *  # noqa: F401,F403
from theustad import TheUstadResult, TheUstadRunner, main as _main

# Deprecated 1.x import aliases.
GateResult = TheUstadResult
GateRunner = TheUstadRunner


def main(argv=None):
    print("GATE_DEPRECATED use theustad.py", file=sys.stderr)
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
