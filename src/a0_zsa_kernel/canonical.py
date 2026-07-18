"""Canonical serialization and hashing.

Canonical JSON rules:
- UTF-8; object keys sorted lexicographically by Unicode code point.
- No insignificant whitespace; arrays retain declared order.
- Strings use JSON escaping with non-ASCII preserved.
- Fixed decimals are strings in non-exponent fixed notation, max six places.
- Timestamps are UTC, second precision, and end in ``Z``.
- Enums serialize to their uppercase values; explicit nulls are preserved.
- Duplicate JSON object keys are invalid at the CLI boundary.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


def _normalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="python", exclude_none=False)
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        utc = value.astimezone(timezone.utc).replace(microsecond=0)
        return utc.isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_id(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def loads_no_duplicates(raw: str) -> Any:
    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=hook, parse_float=Decimal, parse_int=int)
