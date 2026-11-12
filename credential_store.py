"""Explicit credential placeholders; not comprehensive PII redaction."""

import re

_TOKEN = re.compile(r"\{\{([a-zA-Z][a-zA-Z0-9_]*\.(?:username|password))\}\}")


class CredentialStore:
    def __init__(self, values: dict[str, str], *, allowed_origin=None):
        if not isinstance(values, dict):
            raise ValueError("Credentials must be a mapping")
        for key, value in values.items():
            if (
                not isinstance(key, str)
                or _TOKEN.fullmatch("{{" + key + "}}") is None
                or not isinstance(value, str)
                or not value.strip()
                or "{{" in value
                or "}}" in value
            ):
                raise ValueError("Invalid credential entry")
        self._values = dict(values)
        self._allowed_origin = (
            self._origin(allowed_origin) if allowed_origin is not None else None
        )

    def __repr__(self):
        return "<CredentialStore redacted>"

    @staticmethod
    def _origin(url):
        from urllib.parse import urlsplit

        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == "https" else 80
            return parsed.scheme, parsed.hostname.lower(), port
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid credential origin") from None

    def resolve_fill(self, value: str, *, url=None) -> str:
        """Resolve only a whole-value placeholder, never embedded expressions."""
        match = _TOKEN.fullmatch(value)
        if match is None:
            if "{{" in value or "}}" in value:
                raise ValueError("Credential placeholder must be the entire fill value")
            return value
        if self._allowed_origin is not None:
            if self._origin(url) != self._allowed_origin:
                raise ValueError("Credential fill blocked outside allowed origin")
        if match[1] not in self._values:
            raise ValueError("Unknown credential placeholder")
        return self._values[match[1]]

    def redact(self, value):
        """Replace known raw values in JSON-like data; keys remain unchanged."""
        if isinstance(value, str):
            for secret in sorted(set(self._values.values()), key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, dict):
            return {key: self.redact(item) for key, item in value.items()}
        return value


def load_credentials(path=None, *, environ=None, allowed_origin=None) -> CredentialStore:
    """Load flat JSON entries; explicit CLOUDQA_CUSTOMER_* env values override."""
    import json
    import os
    from pathlib import Path

    values = {}
    if path is not None:
        try:
            values = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            raise ValueError("Cannot read or parse credential file") from None
        # Validate file data before applying environment overrides.
        CredentialStore(values)

    environment = os.environ if environ is None else environ
    for field in ("username", "password"):
        name = "CLOUDQA_CUSTOMER_" + field.upper()
        if name in environment:
            values["customer." + field] = environment[name]
    return CredentialStore(values, allowed_origin=allowed_origin)
