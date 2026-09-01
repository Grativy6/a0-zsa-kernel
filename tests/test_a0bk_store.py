from __future__ import annotations

import sqlite3

import pytest

from a0bk_kernel.accounting import (
    AccountTransitionReceiptPayload,
    CutDeclaration,
    OpeningBundle,
    TestReceiptPayload,
    open_root,
    open_version,
)
from a0bk_kernel.accounting import (
    append_receipt as make_append_receipt,
)
from a0bk_kernel.canonical import canonical_bytes, sha256_id
from a0bk_kernel.store import LedgerError, SQLiteLedger


def _ref(label: str) -> str:
    return sha256_id({"label": label})


def _opening(label: str = "ledger") -> OpeningBundle:
    cut = CutDeclaration(
        cut_ref=_ref(f"cut:{label}"),
        supplied_by="independent-test",
        scope=f"scope:{label}",
        distinction_summary="supplied fixture distinction",
        witness_refs=(_ref(f"witness:{label}"),),
        limitations=("fixture only",),
    )
    return open_root(label, cut, limitations=("local SQLite profile",))


def _test_receipt(opening: OpeningBundle, *, outcome: str, order: int = 1):
    payload = TestReceiptPayload(
        test_id=f"test:{outcome}",
        subject_ref=opening.account.account_id,
        outcome=outcome,
        evidence_refs=(_ref(f"evidence:{outcome}"),),
        limitations=("test evidence is not closure",),
    )
    return make_append_receipt(
        opening.account,
        payload,
        admission_order=order,
        prior_links=(opening.cut_receipt.header.receipt_id,),
    )


def test_object_store_is_content_addressed_and_idempotent(tmp_path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    value = {"kind": "fixture", "count": 1}
    first = ledger.put_object(value)
    second = ledger.put_object({"count": 1, "kind": "fixture"})
    assert first == second
    assert ledger.get_object(first) == canonical_bytes(value)
    assert ledger.counts()["objects"] == 1
    assert ledger.verify() == []


def test_opening_commit_is_atomic_and_exact_replay_is_idempotent(tmp_path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    opening = _opening()
    ledger.commit_opening(opening)
    ledger.commit_opening(opening)
    assert ledger.counts() == {
        "objects": 0,
        "accounts": 1,
        "receipts": 1,
        "serial_tokens": 0,
    }

    rewritten_account = opening.account.model_copy(
        update={"limitations": ("different bytes under same account/version",)}
    )
    conflicting = opening.model_copy(update={"account": rewritten_account})
    with pytest.raises(LedgerError, match="rewrite"):
        ledger.commit_opening(conflicting)
    assert ledger.counts()["accounts"] == 1
    assert ledger.counts()["receipts"] == 1
    assert ledger.verify() == []


def test_receipt_append_is_idempotent_and_order_conflict_rolls_back(tmp_path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    opening = _opening("append")
    ledger.commit_opening(opening)

    passed = _test_receipt(opening, outcome="PASS")
    ledger.append_receipt(opening.account, passed)
    ledger.append_receipt(opening.account, passed)
    assert ledger.counts()["receipts"] == 2

    failed_same_order = _test_receipt(opening, outcome="FAIL")
    with pytest.raises(LedgerError, match="conflicts"):
        ledger.append_receipt(opening.account, failed_same_order)
    assert ledger.counts()["receipts"] == 2
    assert ledger.verify() == []


def test_version_commit_requires_present_exact_immediate_predecessor(tmp_path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    opening = _opening("version")
    ledger.commit_opening(opening)
    transition = AccountTransitionReceiptPayload(
        prior_version_ref=sha256_id(opening.account),
        next_version=2,
        transition_delta_refs=(_ref("version-delta"),),
        continuity_witness_refs=(_ref("continuity"),),
        preserved_scope="same account",
        limitations=("declared continuity only",),
    )
    version = open_version(opening.account, transition)
    ledger.commit_version(version)
    ledger.commit_version(version)
    assert ledger.counts()["accounts"] == 2
    assert ledger.counts()["receipts"] == 2
    assert ledger.verify() == []

    missing_ledger = SQLiteLedger(tmp_path / "missing.sqlite3")
    with pytest.raises(LedgerError, match="prior account version is absent"):
        missing_ledger.commit_version(version)
    assert missing_ledger.counts()["accounts"] == 0
    assert missing_ledger.counts()["receipts"] == 0


def test_serial_token_has_one_competing_consumer_and_exact_replay(tmp_path) -> None:
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    token = _ref("serial-token")
    decision = _ref("decision-a")
    ledger.register_token(token)
    ledger.register_token(token)
    assert ledger.consume_token(token, decision) is True
    assert ledger.consume_token(token, decision) is False
    with pytest.raises(LedgerError, match="another decision"):
        ledger.consume_token(token, _ref("decision-b"))
    with pytest.raises(LedgerError, match="not registered"):
        ledger.consume_token(_ref("missing-token"), decision)
    assert ledger.counts()["serial_tokens"] == 1
    assert ledger.verify() == []


def test_get_object_refuses_digest_tampering(tmp_path) -> None:
    database = tmp_path / "ledger.sqlite3"
    ledger = SQLiteLedger(database)
    object_ref = ledger.put_object({"original": True})
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE objects SET canonical_bytes = ? WHERE object_ref = ?",
            (canonical_bytes({"tampered": True}), object_ref),
        )
    with pytest.raises(LedgerError, match="digest mismatch"):
        ledger.get_object(object_ref)


def test_full_ledger_verify_reports_object_tampering(tmp_path) -> None:
    database = tmp_path / "ledger.sqlite3"
    ledger = SQLiteLedger(database)
    object_ref = ledger.put_object({"original": True})
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE objects SET canonical_bytes = ? WHERE object_ref = ?",
            (canonical_bytes({"tampered": True}), object_ref),
        )
    errors = ledger.verify()
    assert any(error.startswith("object_") for error in errors), errors


def test_verify_reports_tampered_account_and_receipt_bytes(tmp_path) -> None:
    database = tmp_path / "ledger.sqlite3"
    ledger = SQLiteLedger(database)
    opening = _opening("tamper")
    ledger.commit_opening(opening)
    receipt = _test_receipt(opening, outcome="PASS")
    ledger.append_receipt(opening.account, receipt)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE accounts SET header_bytes = ? WHERE account_id = ? AND version = 1",
            (b"{}", opening.account.account_id),
        )
        connection.execute(
            "UPDATE receipts SET receipt_bytes = ? WHERE receipt_id = ?",
            (b"{}", receipt.header.receipt_id),
        )
    errors = ledger.verify()
    assert any(error.startswith("account_parse:") for error in errors)
    assert any(error.startswith("receipt_parse:") for error in errors)
