"""vulndb-cli — command-line client for vulndb-ui's catalog API.

A thin, dependency-free Python wrapper around vulndb-ui's HTTP API for scripting the catalog and
its attachments without opening the web UI. Ported from the original Node cli.js so the rest of
the (Python) ecosystem can depend on it.

Run as `python3 -m vulndb_cli`. The version is the single source of truth (pyproject reads it).
"""

__version__ = "0.1.0"
