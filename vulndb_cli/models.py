"""Catalog enums and client-side validation — the small shared surface with vulndb-ui's server.

These mirror vulndb-ui's server.js (and the schema documented in its docs/api.md). They are
duplicated across languages on purpose: vulndb-cli is Python and the server is Node, and the
authoritative contract is the HTTP API, not importable code. docs/api.md (in the vulndb-ui repo)
is the single source of truth; if the two ever disagree, the server wins and this is a bug.
"""

PLATFORMS = ["linux", "windows", "other"]
CATEGORIES = ["misconfiguration", "service", "vulnerability"]
TYPES = ["bash", "powershell", "command"]


def validate(config):
    """Return an error string for a configuration dict, or None if it is sound.

    Mirrors vulndb-ui's server-side validateConfiguration() so a bad enum is caught before the
    round trip, with the same message shape.
    """
    if not config.get("name") or not str(config["name"]).strip():
        return "name is required"
    if config.get("platform") not in PLATFORMS:
        return f"platform must be one of {', '.join(PLATFORMS)}"
    if config.get("category") not in CATEGORIES:
        return f"category must be one of {', '.join(CATEGORIES)}"
    if config.get("type") not in TYPES:
        return f"type must be one of {', '.join(TYPES)}"
    if not isinstance(config.get("script"), str):
        return "script must be a string"
    return None
