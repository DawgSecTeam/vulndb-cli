# vulndb-cli

Command-line client for **vulndb-ui's** catalog HTTP API. Script the catalog and its attachments
without opening the web UI. Stdlib-only Python (no third-party deps); ported from vulndb-ui's
original Node `cli.js`.

> For agent/integration context — layout, the ecosystem map, and the contract this client targets —
> see **[AGENTS.md](AGENTS.md)**. The full command reference is in **[docs/cli.md](docs/cli.md)**.

## What it is

`vulndb-cli` talks to a running **vulndb-ui** (the catalog server: MySQL + HTTP API + MinIO
media). Read configurations, create/update/delete them, manage attachments, and trigger/list/
restore backups — all scriptable, all over the same HTTP API the web UI uses. It is the
**sanctioned client** for the catalog: the other Python tools (huitzilopochtli's boxbuilder) shell
out to it rather than calling the API directly.

## Setup

```bash
pip install -e .     # optional — `python3 -m vulndb_cli` runs from a plain directory copy too
```

No dependencies. Point it at vulndb-ui with `VULNDB_UI_URL` (the same env var nakon uses):

```bash
export VULNDB_UI_URL=http://127.0.0.1:3000
```

## Quickstart

```bash
python3 -m vulndb_cli list                          # browse the catalog
python3 -m vulndb_cli list --category misconfiguration --json
python3 -m vulndb_cli get suid-find                 # one config as JSON

python3 -m vulndb_cli describe suid-find "Sets the SUID bit on find …" --yes
echo '{"name":"x","platform":"linux","category":"misconfiguration","type":"bash","script":"id"}' \
  | python3 -m vulndb_cli create --file - --yes
python3 -m vulndb_cli update suid-find --description "new text" --yes
python3 -m vulndb_cli delete suid-find --yes

python3 -m vulndb_cli upload suid-find ./payload.sh --yes
python3 -m vulndb_cli download 42 ./out.bin

python3 -m vulndb_cli backup --yes
python3 -m vulndb_cli list-backups
```

**Output convention:** progress and confirmations → **stderr**; the result and `--json` →
**stdout**. Write commands print what they're about to do and ask first; `--yes` skips the prompt
and is **required** when stdin isn't a terminal (i.e. for any agent or script).

## Using vulndb-cli from another project

Invoke as a subprocess and parse JSON from stdout. huitzilopochtli consumes it this way, as a git
submodule at `vendor/vulndb-cli`. Logs and prompts go to stderr, so stdout is clean to parse.

```bash
python3 -m vulndb_cli list --json                 # → a JSON array of configurations
python3 -m vulndb_cli create --file - --yes <<<"$json"   # → the created row as JSON
```

Base URL resolution: `--url` flag → `$VULNDB_UI_URL` → `http://127.0.0.1:3000`.

## Releasing

1. Bump `__version__` in `vulndb_cli/__init__.py`.
2. Add a `CHANGELOG.md` entry.
3. `git tag vX.Y.Z && git push --tags`.

The version is a single static string (not setuptools-scm): vulndb-cli runs from bare directory
copies with no git history, so the version must be readable with nothing installed.

## Security note

The vulndb-ui API has **no authentication** and the catalog is shared team state — a write here is
immediately live for everyone. That's what the confirmation prompt is for. Keep vulndb-ui on a
trusted network.
