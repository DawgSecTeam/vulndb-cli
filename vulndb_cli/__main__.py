"""`python3 -m vulndb_cli` entry point. No console_script — a plain directory copy behaves the
same as an install, mirroring nakon."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
