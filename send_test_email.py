#!/usr/bin/env python3
"""Legacy wrapper for `main.py test-email`."""

import sys

from main import main as main_entry


def main():
    return main_entry(["test-email", *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
