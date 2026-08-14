"""Stdlib HTTP client for vulndb-ui's catalog API.

No third-party dependencies — urllib only — so vulndb-cli runs anywhere Python does, the way the
original Node cli.js ran anywhere Node did. The API itself (endpoints, shapes, the {error} /
{error, dependents} failure convention) is documented in vulndb-ui's docs/api.md; that file is the
contract this module codes against.
"""

import json
import os
from typing import Optional
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

DEFAULT_URL = "http://127.0.0.1:3000"


class VulndbError(Exception):
    """A failed request, or a precondition the caller violated (bad ref, bad file, …)."""


def resolve_base_url(explicit=None):
    """--url > $VULNDB_UI_URL > http://127.0.0.1:3000.

    Same env var name nakon uses, so one VULNDB_UI_URL covers both tools.
    """
    return (explicit or os.environ.get("VULNDB_UI_URL") or DEFAULT_URL).rstrip("/")


def _request(method, url, body=None, headers=None, timeout=30, parse_json=True):
    """One urllib request. `body` is raw bytes for JSON, or bytes for a multipart upload.

    Returns the parsed JSON for JSON endpoints, or raw bytes when parse_json is False (downloads).
    """
    req = urlrequest.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urlerror.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        detail = text
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("error"):
                detail = parsed["error"]
                if parsed.get("dependents"):
                    detail += f"\ndepended on by: {', '.join(parsed['dependents'])}"
        except (ValueError, TypeError):
            pass  # not JSON — show the raw body
        raise VulndbError(f"{method} {url} -> {exc.code} {exc.reason}\n{detail}") from exc
    except urlerror.URLError as exc:
        raise VulndbError(f"could not reach vulndb-ui at {url}: {exc.reason}") from exc

    if not parse_json:
        return raw
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise VulndbError(f"{url} returned non-JSON body: {exc}") from exc


def _json_request(method, base, path, body=None, query=None, timeout=30):
    url = _url(base, path, query)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else None
    return _request(method, url, payload, headers, timeout=timeout)


def _url(base, path, query=None):
    url = f"{base}{path}"
    if query:
        qs = urlparse.urlencode({k: v for k, v in query.items() if v is not None})
        url = f"{url}?{qs}" if qs else url
    return url


# ---------------------------------------------------------------- catalog read

def all_configurations(base, limit=None, offset=None, timeout=30):
    """GET /api/configurations — the whole table (each row embeds its `attachments`)."""
    return _json_request("GET", base, "/api/configurations",
                         query={"limit": limit, "offset": offset}, timeout=timeout)


def resolve_ref(base, ref, timeout=30):
    """Find a configuration by id or name. `name` is the join key; `id` only appears in URLs."""
    for config in all_configurations(base, timeout=timeout):
        if str(config.get("id")) == str(ref) or config.get("name") == ref:
            return config
    raise VulndbError(f"no configuration with id or name {ref!r}")


# ---------------------------------------------------------------- catalog write

def create_configuration(base, config, timeout=30):
    return _json_request("POST", base, "/api/configurations", body=config, timeout=timeout)


def update_configuration(base, config_id, config, timeout=30):
    return _json_request("PUT", base, f"/api/configurations/{config_id}",
                         body=config, timeout=timeout)


def delete_configuration(base, config_id, timeout=30):
    _json_request("DELETE", base, f"/api/configurations/{config_id}", timeout=timeout)


# ---------------------------------------------------------------- attachments

def _multipart(file_field, filename, data):
    """Hand-built single-part multipart/form-data — urllib has no multipart client."""
    boundary = "----vulndbcli-boundary"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + data + tail
    return body, f"multipart/form-data; boundary={boundary}"


def upload_attachment(base, config_id, filename, data, timeout=120):
    body, content_type = _multipart("file", filename, data)
    return _request("POST", _url(base, f"/api/configurations/{config_id}/attachments"),
                    body, {"Content-Type": content_type}, timeout=timeout)


def rename_attachment(base, attachment_id, new_name, timeout=30):
    return _json_request("PUT", base, f"/api/attachments/{attachment_id}",
                         body={"original_name": new_name}, timeout=timeout)


def delete_attachment(base, attachment_id, timeout=30):
    _json_request("DELETE", base, f"/api/attachments/{attachment_id}", timeout=timeout)


def download_attachment(base, attachment_id, timeout=120):
    """GET /api/attachments/:id/download — raw bytes (the endpoint 302-redirects to MinIO)."""
    return _request("GET", _url(base, f"/api/attachments/{attachment_id}/download"),
                    parse_json=False, timeout=timeout)


# ---------------------------------------------------------------- backups

def trigger_backup(base, timeout=30):
    return _json_request("POST", base, "/api/backups", timeout=timeout)


def list_backups(base, timeout=30):
    return _json_request("GET", base, "/api/backups", timeout=timeout)


def restore_backup(base, filename, timeout=30):
    return _json_request("POST", base, f"/api/backups/{urlparse.quote(filename)}/restore",
                         timeout=timeout)


def download_backup(base, filename, timeout=120):
    return _request("GET", _url(base, f"/api/backups/{urlparse.quote(filename)}/download"),
                    parse_json=False, timeout=timeout)


def delete_backup(base, filename, timeout=30):
    _json_request("DELETE", base, f"/api/backups/{urlparse.quote(filename)}", timeout=timeout)


def upload_backup(base, filename, data, timeout=120):
    body, content_type = _multipart("file", filename, data)
    return _request("POST", _url(base, "/api/backups/upload"),
                    body, {"Content-Type": content_type}, timeout=timeout)
