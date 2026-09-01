from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from a0bk_kernel.canonical import (
    CanonicalJSONError,
    canonical_bytes,
    canonical_text,
    load_bytes_strict,
    loads_strict,
    sha256_id,
)


@pytest.mark.parametrize(
    "text",
    [
        '{"value":1.0}',
        '{"value":1e0}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-0}',
        '{"value":1,"value":2}',
        '\ufeff{"value":1}',
    ],
)
def test_strict_json_boundary_rejects_ambiguous_tokens(text: str) -> None:
    with pytest.raises(CanonicalJSONError):
        loads_strict(text)


def test_strict_byte_boundary_rejects_invalid_utf8() -> None:
    with pytest.raises(CanonicalJSONError, match="strict UTF-8"):
        load_bytes_strict(b'\xff{"value":1}')


def test_canonical_requirement_rejects_noncanonical_spelling() -> None:
    with pytest.raises(CanonicalJSONError, match="not canonical"):
        loads_strict('{"z":1, "a":2}', require_canonical=True)

    assert loads_strict('{"a":2,"z":1}', require_canonical=True) == {
        "a": 2,
        "z": 1,
    }


def test_json_number_and_fixed_decimal_string_cannot_collapse_at_raw_boundary() -> None:
    accepted = loads_strict('{"value":"1.0"}')
    assert accepted == {"value": "1.0"}
    with pytest.raises(CanonicalJSONError):
        loads_strict('{"value":1.0}')


@pytest.mark.parametrize(
    "value",
    [
        1.5,
        Decimal("1"),
        {"nested": [1.5]},
        {1: "non-string key"},
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, 0, 0, 0, 1, tzinfo=UTC),
    ],
)
def test_programmatic_boundary_rejects_noncanonical_values(value: object) -> None:
    with pytest.raises(CanonicalJSONError):
        canonical_bytes(value)


def test_programmatic_boundary_rejects_cycles() -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    with pytest.raises(CanonicalJSONError, match="cyclic"):
        canonical_bytes(cycle)


def test_canonical_identity_is_deterministic_and_order_independent() -> None:
    first = {
        "z": 3,
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "weight": "0.250000",
        "a": True,
    }
    second = {
        "a": True,
        "weight": "0.250000",
        "timestamp": datetime(
            2025,
            12,
            31,
            19,
            tzinfo=timezone(timedelta(hours=-5)),
        ),
        "z": 3,
    }
    assert canonical_text(first) == canonical_text(second)
    assert canonical_bytes(first) == canonical_bytes(second)
    assert sha256_id(first) == sha256_id(second)
