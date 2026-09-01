"""Strict canonical JSON and content identity for the successor kernel.

The legacy prototype intentionally remains unchanged.  This module uses a
stricter boundary: arbitrary JSON floating-point tokens are refused instead
of being normalized into the same representation as fixed-decimal strings.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class CanonicalJSONError(ValueError):
    """Raised when a value has no unambiguous successor-profile encoding."""


def _reject_float(token: str) -> None:
    raise CanonicalJSONError(f"binary/exponent JSON number is forbidden: {token}")


def _reject_constant(token: str) -> None:
    raise CanonicalJSONError(f"non-finite JSON number is forbidden: {token}")


def _parse_int(token: str) -> int:
    if token == "-0":
        raise CanonicalJSONError("negative zero is forbidden")
    return int(token)


def _pairs_without_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CanonicalJSONError(f"duplicate JSON object name: {key}")
        value[key] = item
    return value


def _normalize(value: Any, *, _ancestors: set[int] | None = None) -> Any:
    ancestors = set() if _ancestors is None else _ancestors
    if hasattr(value, "a0bk_canonical_value"):
        # Typed models own the conversion of schema-declared decimals and
        # timestamps to JSON values. Bare programmatic Decimal values below
        # remain forbidden so they cannot collide with arbitrary strings.
        value = value.a0bk_canonical_value()
    elif hasattr(value, "model_dump"):
        raise CanonicalJSONError(
            "foreign model is forbidden; supply explicit canonical JSON values"
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise CanonicalJSONError("binary floating-point values are forbidden")
    if isinstance(value, Decimal):
        raise CanonicalJSONError(
            "bare Decimal is forbidden; use a typed model or explicit JSON string"
        )
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CanonicalJSONError("timestamp must include an offset")
        utc = value.astimezone(UTC)
        if utc.microsecond:
            raise CanonicalJSONError("timestamp must use whole-second precision")
        return utc.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in ancestors:
            raise CanonicalJSONError("cyclic JSON array is forbidden")
        ancestors.add(identity)
        try:
            return [_normalize(item, _ancestors=ancestors) for item in value]
        finally:
            ancestors.remove(identity)
    if isinstance(value, dict):
        identity = id(value)
        if identity in ancestors:
            raise CanonicalJSONError("cyclic JSON object is forbidden")
        ancestors.add(identity)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CanonicalJSONError("JSON object names must be strings")
                normalized[key] = _normalize(item, _ancestors=ancestors)
            return normalized
        finally:
            ancestors.remove(identity)
    raise CanonicalJSONError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_text(value: Any) -> str:
    """Return deterministic UTF-8 JSON text without a trailing newline."""

    try:
        return json.dumps(
            _normalize(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalJSONError(str(exc)) from exc


def canonical_bytes(value: Any) -> bytes:
    return canonical_text(value).encode("utf-8", errors="strict")


def sha256_id(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def loads_strict(text: str, *, require_canonical: bool = False) -> Any:
    if text.startswith("\ufeff"):
        raise CanonicalJSONError("UTF-8 BOM is forbidden")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_float=_reject_float,
            parse_int=_parse_int,
            parse_constant=_reject_constant,
        )
    except CanonicalJSONError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise CanonicalJSONError(str(exc)) from exc
    normalized = _normalize(value)
    if require_canonical and text != canonical_text(normalized):
        raise CanonicalJSONError("JSON input is not canonical")
    return normalized


def load_bytes_strict(data: bytes, *, require_canonical: bool = False) -> Any:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CanonicalJSONError("input is not strict UTF-8") from exc
    return loads_strict(text, require_canonical=require_canonical)


__all__ = [
    "CanonicalJSONError",
    "canonical_bytes",
    "canonical_text",
    "load_bytes_strict",
    "loads_strict",
    "raw_sha256",
    "sha256_id",
]
