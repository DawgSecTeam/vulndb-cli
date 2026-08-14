"""Command-line interface for vulndb-cli.

Mirrors the original Node cli.js command-for-command. Conventions match nakon (and the rest of
the ecosystem): progress and confirmations go to stderr, the command's result goes to stdout,
and `--json` prints a single JSON document. The catalog is shared team state and the API has no
authentication, so every command that writes prints what it is about to do and asks first;
`--yes` skips the prompt (and is required when stdin isn't a terminal — i.e. for any agent/script).
"""

import argparse
import json
import os
import sys

from . import __version__
from .client import (
    VulndbError,
    all_configurations,
    create_configuration,
    delete_attachment,
    delete_backup,
    delete_configuration,
    download_attachment,
    download_backup,
    rename_attachment,
    resolve_base_url,
    resolve_ref,
    restore_backup,
    trigger_backup,
    list_backups,
    update_configuration,
    upload_attachment,
    upload_backup,
)
from .models import CATEGORIES, PLATFORMS, TYPES, validate


def _log(message=""):
    print(message, file=sys.stderr)


def _emit_json(obj):
    print(json.dumps(obj, indent=2))


def _confirm(summary, assume_yes):
    _log(summary)
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise VulndbError("refusing to write without confirmation — re-run with --yes")
    answer = input("proceed? (y/N) ").strip().lower()
    if answer != "y":
        raise VulndbError("aborted")


def _read_input(spec):
    # "-" means stdin, so `… | vulndb-cli create --file -` works.
    if spec == "-":
        return sys.stdin.read()
    if not os.path.isfile(spec):
        raise VulndbError(f"no such file: {spec}")
    with open(spec, "r", encoding="utf-8") as handle:
        return handle.read()


def _read_json_input(spec):
    raw = _read_input(spec)
    try:
        return json.loads(raw)
    except ValueError as exc:
        where = "stdin" if spec == "-" else spec
        raise VulndbError(f"{where} is not valid JSON: {exc}") from exc


def _format_bytes(n):
    if n < 1024:
        return f"{n} B"
    value, unit = n / 1024, "KB"
    for next_unit in ("MB", "GB"):
        if value < 1024:
            break
        value, unit = value / 1024, next_unit
    return f"{value:.1f} {unit}"


def _summarize(config):
    script = config.get("script") or ""
    return "\n".join([
        f"  name        {config.get('name')}",
        f"  platform    {config.get('platform')}",
        f"  category    {config.get('category')}",
        f"  type        {config.get('type')}",
        f"  run_as      {config.get('run_as') or 'root'}",
        f"  description {(str(config['description'])[:120]) if config.get('description') else '(none)'}",
        f"  depends_on  {json.dumps(config.get('depends_on') or [])}",
        f"  script      {script.count(chr(10)) + 1} line(s), {len(script)} bytes",
    ])


def _config_from_args(args, seed):
    """Assemble a configuration from --file and/or flags. Flags win over the file."""
    config = dict(seed)
    if args.file:
        config.update(_read_json_input(args.file))
    if args.name is not None:
        config["name"] = args.name
    if args.description is not None:
        config["description"] = None if args.description == "" else args.description
    if args.platform is not None:
        config["platform"] = args.platform
    if args.category is not None:
        config["category"] = args.category
    if args.type is not None:
        config["type"] = args.type
    if args.run_as is not None:
        config["run_as"] = args.run_as
    if args.script_file is not None:
        config["script"] = _read_input(args.script_file)
    if args.depends_on is not None:
        try:
            config["depends_on"] = json.loads(args.depends_on)
        except ValueError as exc:
            raise VulndbError(f"--depends-on must be a JSON array: {exc}") from exc
    # The server allows empty scripts (depends_on-only rows); come through as '' not None.
    if config.get("script") is None:
        config["script"] = ""
    return config


# ---------------------------------------------------------------- read

def cmd_list(args):
    base = resolve_base_url(args.url)
    search = (args.search or "").lower()
    configs = all_configurations(base, limit=args.limit, offset=args.offset)
    if args.platform:
        configs = [c for c in configs if c.get("platform") == args.platform]
    if args.category:
        configs = [c for c in configs if c.get("category") == args.category]
    if search:
        configs = [
            c for c in configs
            if search in f"{c.get('name', '')} {c.get('description') or ''} {c.get('script') or ''}".lower()
        ]
    configs.sort(key=lambda c: c.get("id", 0))

    if args.json:
        _emit_json(configs)
        return 0

    for config in configs:
        attachments = config.get("attachments") or []
        suffix = f"  [{len(attachments)} attachment{'s' if len(attachments) != 1 else ''}]" if attachments else ""
        print(f"{str(config.get('id')):>4}  {(config.get('platform') or ''):<8} "
              f"{(config.get('category') or ''):<16} {config.get('name')}{suffix}")
        desc = config.get("description")
        print(f"        {' '.join(desc.split()) if desc else '(no description)'}")
    _log(f"\n{len(configs)} configuration(s)")
    return 0


def cmd_get(args):
    base = resolve_base_url(args.url)
    _emit_json(resolve_ref(base, args.ref))
    return 0


# ---------------------------------------------------------------- write

def cmd_create(args):
    base = resolve_base_url(args.url)
    config = _config_from_args(args, {
        "platform": "linux", "category": "misconfiguration",
        "type": "bash", "run_as": "root", "script": "", "depends_on": [],
    })
    invalid = validate(config)
    if invalid:
        raise VulndbError(invalid)
    _confirm(f"create configuration on {base}:\n{_summarize(config)}", args.yes)
    _emit_json(create_configuration(base, config))
    return 0


def cmd_update(args):
    base = resolve_base_url(args.url)
    existing = resolve_ref(base, args.ref)
    # PUT is a full replace, so start from the current row and layer changes on top.
    current = {k: v for k, v in existing.items() if k not in ("attachments", "id")}
    config = _config_from_args(args, current)
    invalid = validate(config)
    if invalid:
        raise VulndbError(invalid)

    changed = [k for k in config if json.dumps(config[k], sort_keys=True) != json.dumps(current.get(k), sort_keys=True)]
    if not changed:
        _log(f"no changes for {existing.get('name')} (id {existing.get('id')})")
        return 0
    diff = "\n".join(
        f"  {k}: {json.dumps(current.get(k))[ :80]} -> {json.dumps(config[k])[ :80]}"
        for k in changed
    )
    _confirm(f"update {existing.get('name')} (id {existing.get('id')}) on {base}:\n{diff}", args.yes)
    _emit_json(update_configuration(base, existing["id"], config))
    return 0


def cmd_describe(args):
    base = resolve_base_url(args.url)
    text = " ".join(args.text)
    existing = resolve_ref(base, args.ref)
    current = {k: v for k, v in existing.items() if k not in ("attachments", "id")}
    config = dict(current, description=text)
    _confirm(
        f"describe {existing.get('name')} (id {existing.get('id')}) on {base}:\n"
        f"  was: {existing.get('description') or '(none)'}\n  now: {text}",
        args.yes,
    )
    update_configuration(base, existing["id"], config)
    _log(f"described {existing.get('name')}")
    return 0


def cmd_delete(args):
    base = resolve_base_url(args.url)
    existing = resolve_ref(base, args.ref)
    attachments = existing.get("attachments") or []
    _confirm(
        f"delete configuration {existing.get('name')} (id {existing.get('id')}) from {base}, "
        f"along with its {len(attachments)} attachment('s)",
        args.yes,
    )
    delete_configuration(base, existing["id"])
    _log(f"deleted {existing.get('name')}")
    return 0


# ---------------------------------------------------------------- attachments

def cmd_upload(args):
    base = resolve_base_url(args.url)
    if not os.path.isfile(args.file):
        raise VulndbError(f"{args.file} is not a file")
    config = resolve_ref(base, args.ref)
    with open(args.file, "rb") as handle:
        data = handle.read()
    size = len(data)
    attachment = upload_attachment(base, config["id"], os.path.basename(args.file), data)
    _log(f"uploaded {os.path.basename(args.file)} ({size} bytes) -> {config.get('name')}")
    _emit_json(attachment)
    return 0


def cmd_download(args):
    base = resolve_base_url(args.url)
    data = download_attachment(base, args.attachment_id)
    with open(args.outfile, "wb") as handle:
        handle.write(data)
    _log(f"saved {len(data)} bytes to {args.outfile}")
    return 0


def cmd_rename_attachment(args):
    base = resolve_base_url(args.url)
    new_name = args.new_name.strip()
    if not new_name:
        raise VulndbError("usage: rename-attachment <attachmentId> <newName>")
    renamed = rename_attachment(base, args.attachment_id, new_name)
    _log(f"renamed attachment {args.attachment_id} -> {renamed.get('original_name')}")
    _emit_json(renamed)
    return 0


def cmd_delete_attachment(args):
    base = resolve_base_url(args.url)
    delete_attachment(base, args.attachment_id)
    _log(f"deleted attachment {args.attachment_id}")
    return 0


# ---------------------------------------------------------------- backups

def cmd_backup(args):
    base = resolve_base_url(args.url)
    _confirm(f"trigger a backup of the database on {base} now", args.yes)
    backup = trigger_backup(base)
    _log(f"created {backup.get('filename')} ({_format_bytes(backup.get('size_bytes', 0))})")
    return 0


def cmd_list_backups(args):
    base = resolve_base_url(args.url)
    backups = list_backups(base)
    if args.json:
        _emit_json(backups)
        return 0
    for backup in backups:
        _log(f"{backup.get('created_at')}  {_format_bytes(backup.get('size_bytes', 0)):>9}  "
             f"{backup.get('filename')}")
    _log(f"\n{len(backups)} backup(s)")
    return 0


def cmd_restore_backup(args):
    base = resolve_base_url(args.url)
    _confirm(
        f"RESTORE {args.filename} on {base} — this OVERWRITES the live database with this "
        f"backup's contents.\nA fresh safety backup of the current database is taken first.",
        args.yes,
    )
    result = restore_backup(base, args.filename)
    _log(f"restored from {result.get('restored')} "
         f"(safety backup taken first: {result.get('safety_backup')})")
    return 0


def cmd_download_backup(args):
    base = resolve_base_url(args.url)
    data = download_backup(base, args.filename)
    with open(args.outfile, "wb") as handle:
        handle.write(data)
    _log(f"saved {len(data)} bytes to {args.outfile}")
    return 0


def cmd_upload_backup(args):
    base = resolve_base_url(args.url)
    if not os.path.isfile(args.file):
        raise VulndbError(f"{args.file} is not a file")
    with open(args.file, "rb") as handle:
        data = handle.read()
    backup = upload_backup(base, os.path.basename(args.file), data)
    _log(f"uploaded {os.path.basename(args.file)} -> {backup.get('filename')} "
         f"({_format_bytes(backup.get('size_bytes', 0))})")
    return 0


def cmd_delete_backup(args):
    base = resolve_base_url(args.url)
    _confirm(f"delete backup {args.filename} from {base}", args.yes)
    delete_backup(base, args.filename)
    _log(f"deleted {args.filename}")
    return 0


# ---------------------------------------------------------------- parser

def _add_write_options(parser):
    """File/flag options shared by `create` and `update`."""
    parser.add_argument("--file", metavar="json|-", help="a JSON document to create/update from (- = stdin)")
    parser.add_argument("--script-file", metavar="PATH", help="read the script from this file")
    parser.add_argument("--name", metavar="X")
    parser.add_argument("--description", metavar="TEXT",
                        help="set the description (pass an empty string to clear it)")
    parser.add_argument("--platform", choices=PLATFORMS)
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--type", choices=TYPES)
    parser.add_argument("--run-as", dest="run_as", metavar="USER")
    parser.add_argument("--depends-on", dest="depends_on", metavar="JSON",
                        help="a JSON array of dependencies")


def build_parser():
    global_opts = argparse.ArgumentParser(add_help=False)
    global_opts.add_argument("--url", help="vulndb-ui base URL (default: $VULNDB_UI_URL or "
                                           "http://127.0.0.1:3000)")
    global_opts.add_argument("--yes", action="store_true",
                             help="skip the write confirmation prompt (required when stdin "
                                  "isn't a terminal)")

    parser = argparse.ArgumentParser(
        prog="vulndb-cli",
        description="Thin client for vulndb-ui's catalog HTTP API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The catalog is shared team state with no auth; writes ask first (--yes to skip).",
    )
    parser.add_argument("--version", action="version", version=f"vulndb-cli {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list configurations", parents=[global_opts])
    p.add_argument("--platform", choices=PLATFORMS)
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--search", metavar="TEXT", help="substring over name, description and script")
    p.add_argument("--limit", type=int)
    p.add_argument("--offset", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="show one configuration as JSON", parents=[global_opts])
    p.add_argument("ref", metavar="id|name")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("create", help="create a configuration", parents=[global_opts])
    _add_write_options(p)
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("update", help="change some fields, leaving the rest alone",
                       parents=[global_opts])
    p.add_argument("ref", metavar="id|name")
    _add_write_options(p)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("describe", help="set just the description", parents=[global_opts])
    p.add_argument("ref", metavar="id|name")
    p.add_argument("text", nargs="+", metavar="text")
    p.set_defaults(func=cmd_describe)

    p = sub.add_parser("delete", help="delete a configuration and its attachments",
                       parents=[global_opts])
    p.add_argument("ref", metavar="id|name")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("upload", help="attach a file to a configuration", parents=[global_opts])
    p.add_argument("ref", metavar="id|name")
    p.add_argument("file", metavar="file")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("download", help="download an attachment by id", parents=[global_opts])
    p.add_argument("attachment_id", metavar="attachmentId")
    p.add_argument("outfile", metavar="outfile")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("rename-attachment", help="rename an attachment", parents=[global_opts])
    p.add_argument("attachment_id", metavar="attachmentId")
    p.add_argument("new_name", metavar="newName")
    p.set_defaults(func=cmd_rename_attachment)

    p = sub.add_parser("delete-attachment", help="delete an attachment by id",
                       parents=[global_opts])
    p.add_argument("attachment_id", metavar="attachmentId")
    p.set_defaults(func=cmd_delete_attachment)

    p = sub.add_parser("backup", help="trigger a database backup now", parents=[global_opts])
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("list-backups", help="list available backups", parents=[global_opts])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list_backups)

    p = sub.add_parser("restore-backup",
                       help="OVERWRITE the live database from a backup (safety backup taken first)",
                       parents=[global_opts])
    p.add_argument("filename", metavar="filename")
    p.set_defaults(func=cmd_restore_backup)

    p = sub.add_parser("download-backup", help="download a backup file", parents=[global_opts])
    p.add_argument("filename", metavar="filename")
    p.add_argument("outfile", metavar="outfile")
    p.set_defaults(func=cmd_download_backup)

    p = sub.add_parser("upload-backup", help="upload a previously-downloaded backup file",
                       parents=[global_opts])
    p.add_argument("file", metavar="file")
    p.set_defaults(func=cmd_upload_backup)

    p = sub.add_parser("delete-backup", help="delete a backup file", parents=[global_opts])
    p.add_argument("filename", metavar="filename")
    p.set_defaults(func=cmd_delete_backup)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except VulndbError as exc:
        print(str(exc), file=sys.stderr)
        return 1
