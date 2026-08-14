# `vulndb-cli` reference

`vulndb-cli` is a thin, dependency-free (stdlib-only) wrapper around vulndb-ui's own HTTP API
([`api.md`](https://github.com/DawgSecTeam/vulndb-ui) in the vulndb-ui repo) for scripting the
catalog without opening the web UI. Ported from the original Node `cli.js`; the commands and JSON
shapes are unchanged.

```
python3 -m vulndb_cli <command> [args] [--url <vulndb-ui url>] [--yes]
```

(`--url` and `--yes` go after the subcommand. `pip install -e .` is optional — a plain directory
copy runs identically, like nakon.)

**Read:**

| Command | Description |
|---|---|
| `list [--platform P] [--category C] [--search TEXT] [--limit N] [--offset N] [--json]` | List configurations with their descriptions. `--search` matches name, description and script. `--limit`/`--offset` pass through as pagination query params (window the page returned; the client-side `--platform`/`--category`/`--search` filters then apply to that page). `--json` prints full records. |
| `get <id\|name>` | Print one configuration as JSON, including its `attachments` array |

**Write** — every one of these prints what it's about to do and asks first; `--yes` skips the
prompt and is **required** when stdin isn't a terminal:

| Command | Description |
|---|---|
| `create --file <json\|->` | Create a configuration from a JSON document (`-` reads stdin) |
| `create --name X [--platform P] [--category C] [--type T] [--script-file F] [--description TEXT] [--run-as U] [--depends-on JSON]` | The same, from flags |
| `update <id\|name> [--file <json\|->] [--name X] [--description TEXT] …` | Change some fields, leaving the rest alone (prints "no changes" if nothing differs) |
| `describe <id\|name> <text>` | Set just the description |
| `delete <id\|name>` | Delete a configuration and its attachments |

**Attachments:**

| Command | Description |
|---|---|
| `upload <id\|name> <file>` | Upload `<file>` as an attachment on that configuration |
| `download <attachmentId> <outfile>` | Download an attachment by id (follows the presigned MinIO redirect) |
| `rename-attachment <attachmentId> <newName>` | Rename an attachment (display name only) |
| `delete-attachment <attachmentId>` | Delete an attachment by id |

**Backups** — the server backs up the database automatically on a schedule; these are for
on-demand use. `restore-backup` is the one command here more dangerous than `delete` (it
overwrites the live database), so its confirmation prompt says so explicitly — the server also
takes a fresh safety backup of the current database before restoring:

| Command | Description |
|---|---|
| `backup` | Trigger a backup of the database now |
| `list-backups [--json]` | List available backups, newest first |
| `restore-backup <filename>` | **Overwrite the live database** from a backup (a safety backup of the current DB is taken first) |
| `download-backup <filename> <outfile>` | Download a backup file |
| `upload-backup <file>` | Upload a previously-downloaded backup file |
| `delete-backup <filename>` | Delete a backup file |

**Base URL** resolution, in order: the `--url <url>` flag, then `$VULNDB_UI_URL`, then
`http://127.0.0.1:3000`. `VULNDB_UI_URL` is the same env var name nakon uses, so setting it once
in the environment covers both tools.

```bash
python3 -m vulndb_cli list --category misconfiguration
python3 -m vulndb_cli list --search ssh --json
python3 -m vulndb_cli get suid-find
python3 -m vulndb_cli describe suid-find "Sets the SUID bit on find, so any user can read root-owned files." --yes
echo '{"name":"x","platform":"linux","category":"misconfiguration","type":"bash","script":"id"}' \
  | python3 -m vulndb_cli create --file - --yes
python3 -m vulndb_cli upload suid-find ./malicious.conf --yes
VULNDB_UI_URL=http://10.0.0.118:3000 python3 -m vulndb_cli list   # (or pass --url after the subcommand)
python3 -m vulndb_cli backup --yes
python3 -m vulndb_cli list-backups
python3 -m vulndb_cli restore-backup vulndb-backup-2026-08-01T03-00-00-000Z.sql.gz --yes
python3 -m vulndb_cli upload-backup ./vulndb-backup-2026-08-01T03-00-00-000Z.sql.gz
```

`update` and `describe` do a read-modify-write, because `PUT /api/configurations/:id` is a full
replace — passing one field would otherwise blank every other one.

Errors from the API are printed with the response body and exit status 1. A `400` names the field
that was wrong; deleting a configuration something else depends on returns `409` and lists the
dependents. Progress and confirmations go to **stderr**; results and `--json` go to **stdout**.

**Note:** the API has no authentication and the catalog is shared team state, so a write here is
immediately live for everyone. That's what the confirmation prompt is for.
