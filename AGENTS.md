# AGENTS.md — vulndb-cli

Guidance for agents (and humans) working in or against this repo.

## What this is

`vulndb-cli` is the **sanctioned command-line client** for vulndb-ui's catalog HTTP API — read,
create/update/delete configurations, manage attachments, and run on-demand backups. Stdlib-only
Python, ported from vulndb-ui's original Node `cli.js`.

## Ecosystem position

```
vulndb-ui (catalog server: MySQL + HTTP API + MinIO media)
   ▲
   │ HTTP API — vulndb-cli is the only sanctioned client for CRUD/attachments/backups
   │
 vulndb-cli  ◀── submodule + CLI ──  huitzilopochtli (boxbuilder)
```

vulndb-cli is a **shared dependency** (git submodule, invoked as a CLI) of **huitzilopochtli**'s
boxbuilder, which uses it for catalog CRUD + attachment uploads (box theming) instead of calling
vulndb-ui's HTTP API directly. **tezcatlipoca** does *not* depend on it — it reaches the catalog
through nakon (read/build/randomize). The catalog itself lives in **vulndb-ui**; this repo is only
the client.

## Layout

```
vulndb_cli/
  __init__.py     __version__ (single source of truth)
  __main__.py     `python3 -m vulndb_cli` entry
  cli.py          argparse parser + all 17 command handlers
  client.py       stdlib HTTP client (urllib): one helper per endpoint
  models.py       PLATFORMS/CATEGORIES/TYPES + validate() (mirrors server.js)
docs/cli.md       full command reference
```

## Run / build / test

```bash
python3 -m vulndb_cli --version
python3 -m vulndb_cli list --json --url http://127.0.0.1:3000
```

No dependencies, no build step, no test suite. To verify a change, point it at a running vulndb-ui
(or a stub of `/api/configurations` + friends) and exercise a read + a `create --yes` round trip.

## Conventions & gotchas

- **Output contract:** progress/confirmations → **stderr**; the result and `--json` → **stdout**.
  Keep stdout parseable — consumers parse it as JSON.
- **`--url` and `--yes` go after the subcommand** (`vulndb-cli list --url X`), not before.
- **No auth.** The catalog is shared team state; writes are immediately live for everyone. Every
  write command asks first; `--yes` skips it and is required for non-interactive (non-tty) stdin.
- **`name` is the join key** across the ecosystem; `id` only appears in URLs. `get`/`update`/
  `delete`/`upload` accept either.
- **`update`/`describe` are read-modify-write** — `PUT` is a full replace, so they fetch the
  current row and layer changes on top. `update` prints "no changes" when nothing differs.
- **`models.validate()` mirrors `server.js`** but only guards the `--file` path (argparse `choices`
  already catch bad enums passed as flags). If the two ever disagree, the server wins — this is a
  bug here. The authoritative contract is vulndb-ui's `docs/api.md`.
- **Version** lives in `__init__.py:__version__`, read dynamically by pyproject. Static string, not
  setuptools-scm, so a bare directory copy with nothing installed still reports a version.

## Integration contract (for consumers)

Invoke as a subprocess; do not import internals.

```bash
python3 -m vulndb_cli list --json                        # → JSON array of configurations
python3 -m vulndb_cli get <name>                         # → JSON object (incl. attachments)
python3 -m vulndb_cli create --file - --yes <<<"$json"   # → created row as JSON
python3 -m vulndb_cli upload <name> <file> --yes         # → attachment JSON on stdout
```

**Env var:** `VULNDB_UI_URL` (same name nakon uses — one var covers both). Exit code: `0` success,
`1` on any `VulndbError` (unreachable server, non-2xx response, bad ref, declined/aborted write).
