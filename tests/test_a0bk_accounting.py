from __future__ import annotations

import pytest
from pydantic import ValidationError

from a0bk_kernel.accounting import (
    AccountHeader,
    AccountTransitionReceiptPayload,
    ClosureReceiptPayload,
    ClosureStatus,
    CutDeclaration,
    CutReceiptPayload,
    OpeningBundle,
    ResidualOperation,
    ResidualReceiptPayload,
    ResidualStatus,
    TestReceiptPayload,
    VersionOpening,
    append_receipt,
    make_receipt,
    open_child,
    open_root,
    open_successor,
    open_version,
    register_residual,
    transition_residual,
    wrap_legacy_receipt,
)
from a0bk_kernel.canonical import canonical_text, raw_sha256, sha256_id
from a0bk_kernel.models import AccountOperation


def _ref(label: str) -> str:
    return sha256_id({"label": label})


def _cut(label: str) -> CutDeclaration:
    return CutDeclaration(
        cut_ref=_ref(f"cut:{label}"),
        supplied_by="independent-test",
        scope=f"scope:{label}",
        distinction_summary=f"distinction:{label}",
        witness_refs=(_ref(f"witness:{label}"),),
        limitations=("fixture evidence only",),
    )


def test_root_child_and_successor_open_atomically_shaped_accounts() -> None:
    root = open_root("root", _cut("root"), limitations=("bounded",))
    assert root.account.operation is AccountOperation.ROOT
    assert root.account.version == 1
    assert root.cut_receipt.header.account_ref == root.account.account_id
    assert root.cut_receipt.header.admission_order == 0
    assert root.cut_receipt.payload.operation is AccountOperation.ROOT

    child = open_child(
        "child",
        root.account.account_id,
        root.cut_receipt.header.receipt_id,
        _cut("child"),
        limitations=("bounded",),
    )
    assert child.account.operation is AccountOperation.CHILD
    assert child.account.parent_account_ref == root.account.account_id
    assert child.account.parent_receipt_ref == root.cut_receipt.header.receipt_id
    assert child.cut_receipt.header.parent_links == (
        root.account.account_id,
        root.cut_receipt.header.receipt_id,
    )

    successor = open_successor(
        "successor",
        root.account.account_id,
        root.cut_receipt.header.receipt_id,
        _cut("successor"),
        limitations=("bounded",),
    )
    assert successor.account.operation is AccountOperation.SUCCESSOR
    assert successor.account.version == 1
    assert successor.account.account_id != root.account.account_id
    assert successor.account.superseded_account_ref == root.account.account_id
    assert successor.cut_receipt.header.supersedes_links == (
        root.account.account_id,
        root.cut_receipt.header.receipt_id,
    )
    assert successor.account.parent_account_ref is None


def test_opening_bundle_refuses_payload_cut_origin_mismatch() -> None:
    root = open_root("origin-bound", _cut("origin-bound"), limitations=("bounded",))
    mismatched = make_receipt(
        payload=CutReceiptPayload(
            cut=_cut("different-cut"), operation=AccountOperation.ROOT
        ),
        account_ref=root.account.account_id,
        origin_a0_ref=root.account.origin_a0_ref,
        admission_order=0,
    )
    with pytest.raises(ValidationError, match="payload cut"):
        OpeningBundle(account=root.account, cut_receipt=mismatched)


def test_openings_are_deterministic() -> None:
    first = open_root("same", _cut("same"), limitations=("bounded",))
    second = open_root("same", _cut("same"), limitations=("bounded",))
    assert first == second
    assert sha256_id(first) == sha256_id(second)


def test_new_account_identity_cannot_be_replaced_by_caller() -> None:
    root = open_root("identity", _cut("identity"), limitations=("bounded",))
    values = root.account.model_dump(mode="python")
    values["account_id"] = _ref("forged-account-id")
    with pytest.raises(ValidationError, match="opening basis"):
        AccountHeader.model_validate(values)


def test_receipt_identity_binds_header_and_payload() -> None:
    root = open_root(
        "receipt-identity", _cut("receipt-identity"), limitations=("bounded",)
    )
    values = root.cut_receipt.model_dump(mode="python")
    values["header"]["receipt_id"] = _ref("forged-receipt-id")
    with pytest.raises(ValidationError, match="receipt identity"):
        type(root.cut_receipt).model_validate(values)


@pytest.mark.parametrize(
    "values",
    [
        {
            "operation": AccountOperation.ROOT,
            "version": 1,
            "parent_account_ref": _ref("parent-account"),
            "parent_receipt_ref": _ref("parent-receipt"),
        },
        {
            "operation": AccountOperation.CHILD,
            "version": 1,
        },
        {
            "operation": AccountOperation.SUCCESSOR,
            "version": 1,
        },
        {
            "operation": AccountOperation.VERSION,
            "version": 2,
        },
        {
            "operation": AccountOperation.APPEND,
            "version": 1,
        },
    ],
)
def test_illegal_account_opening_variants_are_refused(
    values: dict[str, object],
) -> None:
    base: dict[str, object] = {
        "account_id": _ref("illegal-account"),
        "account_label": "illegal",
        "origin_a0_ref": _ref("origin"),
        "limitations": ("test",),
    }
    with pytest.raises(ValidationError):
        AccountHeader(**base, **values)


def test_version_preserves_identity_and_requires_exact_next_predecessor() -> None:
    root = open_root("versioned", _cut("versioned"), limitations=("bounded",))
    prior_ref = sha256_id(root.account)
    transition = AccountTransitionReceiptPayload(
        prior_version_ref=prior_ref,
        next_version=2,
        transition_delta_refs=(_ref("delta"),),
        continuity_witness_refs=(_ref("continuity"),),
        preserved_scope="same bounded account",
        limitations=("continuity is declared and witnessed only",),
    )
    version = open_version(root.account, transition)
    assert version.account.account_id == root.account.account_id
    assert version.account.origin_a0_ref == root.account.origin_a0_ref
    assert version.account.version == 2
    assert version.account.immediate_prior_version_ref == prior_ref
    assert version.transition_receipt.payload == transition

    wrong_prior = transition.model_copy(
        update={"prior_version_ref": _ref("not-the-prior-header")}
    )
    with pytest.raises(ValueError, match="exact prior"):
        open_version(root.account, wrong_prior)

    skipped = transition.model_copy(update={"next_version": 3})
    with pytest.raises(ValueError, match="exactly one"):
        open_version(root.account, skipped)

    wrong_origin_receipt = make_receipt(
        payload=transition,
        account_ref=version.account.account_id,
        origin_a0_ref=_ref("wrong-version-origin"),
        admission_order=1,
        prior_links=(prior_ref,),
    )
    with pytest.raises(ValidationError, match="origin"):
        VersionOpening(account=version.account, transition_receipt=wrong_origin_receipt)


def test_append_is_a_receipt_operation_not_an_account_opening() -> None:
    root = open_root("append", _cut("append"), limitations=("bounded",))
    payload = TestReceiptPayload(
        test_id="test-1",
        subject_ref=root.account.account_id,
        outcome="PASS",
        evidence_refs=(_ref("test-evidence"),),
        limitations=("test evidence is not closure",),
    )
    receipt = append_receipt(
        root.account,
        payload,
        admission_order=1,
        prior_links=(root.cut_receipt.header.receipt_id,),
    )
    assert receipt.header.account_ref == root.account.account_id
    assert receipt.header.admission_order == 1
    assert receipt.payload.receipt_type == "TestReceipt"
    with pytest.raises(ValueError, match="positive"):
        append_receipt(
            root.account,
            payload,
            admission_order=0,
            prior_links=(root.cut_receipt.header.receipt_id,),
        )
    with pytest.raises(ValueError, match="prior receipt"):
        append_receipt(
            root.account,
            payload,
            admission_order=1,
            prior_links=(),
        )


def test_legacy_wrapper_binds_exact_opaque_bytes_without_status_uplift() -> None:
    legacy_bytes = b'{"not":"parsed",\r\n"status":"PARTIAL"}\r\n'
    payload = wrap_legacy_receipt(
        legacy_bytes,
        legacy_object_id="build-008-packet",
        legacy_schema="BUILD008",
        source_record="frozen source record",
        preserved_scope="internal compatibility only",
        preserved_status="PARTIAL",
        preserved_authority_ceiling="no native pinned-kernel support",
        limitations=("opaque bytes; no semantic uplift",),
    )
    assert payload.exact_content_digest == raw_sha256(legacy_bytes)
    assert payload.preserved_status == "PARTIAL"
    assert payload.preserved_authority_ceiling == "no native pinned-kernel support"
    assert "closure_status" not in payload.model_dump(mode="json")

    changed = wrap_legacy_receipt(
        legacy_bytes.replace(b"PARTIAL", b"PASS"),
        legacy_object_id="build-008-packet",
        legacy_schema="BUILD008",
        source_record="frozen source record",
        preserved_scope="internal compatibility only",
        preserved_status="PARTIAL",
        preserved_authority_ceiling="no native pinned-kernel support",
        limitations=("opaque bytes; no semantic uplift",),
    )
    assert changed.exact_content_digest != payload.exact_content_digest

    package_receipt = make_receipt(
        payload=payload,
        account_ref="PACKAGE_NA",
        origin_a0_ref="ORIGIN_SELF",
        admission_order=0,
    )
    serialized = canonical_text(package_receipt)
    assert '"preserved_status":"PARTIAL"' in serialized
    assert "closure_status" not in serialized


def test_test_receipt_cannot_claim_closure() -> None:
    values = {
        "test_id": "test-closure-refusal",
        "subject_ref": _ref("subject"),
        "outcome": "PASS",
        "evidence_refs": (_ref("evidence"),),
        "limitations": ("a test is not closure",),
        "closure_status": "CLOSED_IN_SCOPE",
    }
    with pytest.raises(ValidationError, match="closure_status"):
        TestReceiptPayload.model_validate(values)

    closure = ClosureReceiptPayload(
        claim_ref=_ref("claim"),
        closure_status=ClosureStatus.CLOSED_IN_SCOPE,
        exact_scope="one exact test claim",
        authority_ceiling="local evidence only",
        supporting_receipt_refs=(_ref("supporting-test-receipt"),),
        limitations=("does not generalize",),
    )
    assert closure.closure_status is ClosureStatus.CLOSED_IN_SCOPE


def test_residual_identity_is_stable_across_carry_and_partial_discharge() -> None:
    registered = register_residual(
        account_ref=_ref("account"),
        scope="mechanic hypothesis",
        burden_summary="unexplained movement residual",
        evidence_refs=(_ref("residual-evidence"),),
        limitations=("local observation only",),
    )
    carry = transition_residual(
        registered,
        operation=ResidualOperation.CARRY,
        prior_receipt_ref=_ref("registered-receipt"),
        resulting_status=ResidualStatus.OPEN,
    )
    partial = transition_residual(
        carry,
        operation=ResidualOperation.PARTIAL_DISCHARGE,
        prior_receipt_ref=_ref("carry-receipt"),
        resulting_status=ResidualStatus.PARTIALLY_DISCHARGED,
        evidence_refs=(_ref("partial-evidence"),),
    )
    assert registered.residual_id == carry.residual_id == partial.residual_id
    assert carry.prior_residual_receipt_refs == (_ref("registered-receipt"),)
    assert partial.prior_residual_receipt_refs == (_ref("carry-receipt"),)


def test_residual_split_requires_coverage_or_an_explicit_remainder() -> None:
    registered = register_residual(
        account_ref=_ref("split-account"),
        scope="split scope",
        burden_summary="compound burden",
        evidence_refs=(),
        limitations=("fixture",),
    )
    with pytest.raises(ValidationError, match="coverage witness or explicit remainder"):
        transition_residual(
            registered,
            operation=ResidualOperation.SPLIT,
            prior_receipt_ref=_ref("prior-split-receipt"),
            resulting_status=ResidualStatus.SUPERSEDED,
            child_residual_ids=(_ref("child-a"), _ref("child-b")),
        )

    split = transition_residual(
        registered,
        operation=ResidualOperation.SPLIT,
        prior_receipt_ref=_ref("prior-split-receipt"),
        resulting_status=ResidualStatus.SUPERSEDED,
        child_residual_ids=(_ref("child-a"), _ref("child-b")),
        coverage_witness_refs=(_ref("coverage"),),
    )
    assert split.residual_id == registered.residual_id
    assert split.resulting_status is ResidualStatus.SUPERSEDED


def test_residual_split_requires_two_distinct_children() -> None:
    registered = register_residual(
        account_ref=_ref("duplicate-child-account"),
        scope="split scope",
        burden_summary="compound burden",
        evidence_refs=(),
        limitations=("fixture",),
    )
    duplicate_child = _ref("same-child")
    with pytest.raises(ValidationError, match="child"):
        ResidualReceiptPayload(
            residual_id=registered.residual_id,
            operation=ResidualOperation.SPLIT,
            resulting_status=ResidualStatus.SUPERSEDED,
            scope=registered.scope,
            burden_summary=registered.burden_summary,
            prior_residual_receipt_refs=(_ref("prior"),),
            child_residual_ids=(duplicate_child, duplicate_child),
            coverage_witness_refs=(_ref("coverage"),),
            limitations=("fixture",),
        )
