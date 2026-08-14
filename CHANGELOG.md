# Changelog

All notable changes to vulndb-cli are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-08-13

Initial release. Extracted from vulndb-ui (where it lived as the Node `cli.js`) into its own
Python repo so the rest of the (Python) ecosystem can depend on it as a standalone, versioned
client.

### Added
- Python port of `cli.js`, stdlib-only (urllib). Same 17 subcommands, same JSON shapes, same
  confirmation/`--yes` model: `list, get, create, update, describe, delete, upload, download,
  rename-attachment, delete-attachment, backup, list-backups, restore-backup, download-backup,
  upload-backup, delete-backup`.
- Entry point `python3 -m vulndb_cli` (no console_script, so a plain directory copy behaves like
  an install).
- `README.md`, `AGENTS.md`, `docs/cli.md` (adapted from vulndb-ui), `CHANGELOG.md`.
- Version single-sourced from `vulndb_cli/__init__.py:__version__`, read dynamically by pyproject.

### Notes
- The catalog enum/validate constants are duplicated between this repo (Python) and vulndb-ui's
  `server.js` (Node). The authoritative contract is vulndb-ui's `docs/api.md`; the duplication is
  unavoidable across languages.
