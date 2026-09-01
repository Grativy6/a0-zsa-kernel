"""Native account, receipt, legacy-reference, and residual primitives.

This is a bounded successor profile.  It preserves the legacy prototype as
evidence and deliberately refuses to infer cuts, continuity, authority, or
closure from a convenient result.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar, Literal, TypeAlias

from pydantic import Field, model_validator

from .canonical import raw_sha256, sha256_id
from .models import AccountOperation, HashRef, StrictModel

NonEmpty = Annotated[str, Field(min_length=1)]


class ABKLifecycle(StrEnum):
    ABK_UNRESOLVED = "ABK_UNRESOLVED"
    ABK_CANDIDATE = "ABK_CANDIDATE"
    ABK_CHECKED = "ABK_CHECKED"
    ABK_MEASURED = "ABK_MEASURED"
    ABK_COMMITTED = "ABK_COMMITTED"
    ABK_REJECTED = "ABK_REJECTED"
    ABK_EXPIRED = "ABK_EXPIRED"
    ABK_REOPENED = "ABK_REOPENED"


class ClosureStatus(StrEnum):
    OPEN = "OPEN"
    UNRESOLVED = "UNRESOLVED"
    CLOSED_IN_SCOPE = "CLOSED_IN_SCOPE"
    REOPENED = "REOPENED"


class ResidualOperation(StrEnum):
    REGISTER = "REGISTER"
    CARRY = "CARRY"
    SPLIT = "SPLIT"
    PARTIAL_DISCHARGE = "PARTIAL_DISCHARGE"
    SCOPED_DISCHARGE = "SCOPED_DISCHARGE"
    REOPEN = "REOPEN"
    SUPERSEDE = "SUPERSEDE"


class ResidualStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_DISCHARGED = "PARTIALLY_DISCHARGED"
    DISCHARGED_IN_SCOPE = "DISCHARGED_IN_SCOPE"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class CutDeclaration(StrictModel):
    """A supplied cut and its witness; the constructor never invents one."""

    cut_ref: HashRef
    supplied_by: NonEmpty
    scope: NonEmpty
    distinction_summary: NonEmpty
    witness_refs: tuple[HashRef, ...] = Field(min_length=1)
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)


class CutReceiptPayload(StrictModel):
    receipt_type: Literal["CutReceipt"] = "CutReceipt"
    cut: CutDeclaration
    operation: Literal[
        AccountOperation.ROOT, AccountOperation.CHILD, AccountOperation.SUCCESSOR
    ]


class AccountTransitionReceiptPayload(StrictModel):
    receipt_type: Literal["AccountTransitionReceipt"] = "AccountTransitionReceipt"
    prior_version_ref: HashRef
    next_version: int = Field(ge=2)
    transition_delta_refs: tuple[HashRef, ...] = Field(min_length=1)
    continuity_witness_refs: tuple[HashRef, ...] = Field(min_length=1)
    preserved_scope: NonEmpty
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)


class LegacyReceiptRefPayload(StrictModel):
    receipt_type: Literal["LegacyReceiptRef"] = "LegacyReceiptRef"
    legacy_object_id: NonEmpty
    legacy_schema: NonEmpty
    exact_content_digest: HashRef
    source_record: NonEmpty
    preserved_scope: NonEmpty
    preserved_status: NonEmpty
    preserved_authority_ceiling: NonEmpty
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)


class MaterialDeltaReceiptPayload(StrictModel):
    receipt_type: Literal["MaterialDeltaReceipt"] = "MaterialDeltaReceipt"
    implicated_model_refs: tuple[HashRef, ...] = Field(min_length=1)
    prior_state_refs: tuple[HashRef, ...] = Field(min_length=1)
    delta_witness_refs: tuple[HashRef, ...] = Field(min_length=1)
    changed_fields: tuple[NonEmpty, ...] = Field(min_length=1)
    unchanged_fields: tuple[NonEmpty, ...] = Field(default_factory=tuple)
    rationale_summary: NonEmpty


class LifecycleTransitionReceiptPayload(StrictModel):
    receipt_type: Literal["LifecycleTransitionReceipt"] = "LifecycleTransitionReceipt"
    subject_ref: HashRef
    prior_lifecycle: ABKLifecycle
    resulting_lifecycle: ABKLifecycle
    material_delta_ref: HashRef | None = None
    basis_refs: tuple[HashRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reopening_needs_delta(self) -> LifecycleTransitionReceiptPayload:
        if self.resulting_lifecycle is ABKLifecycle.ABK_REOPENED:
            if self.material_delta_ref is None:
                raise ValueError("ABK_REOPENED requires a material delta receipt")
        elif self.material_delta_ref is not None:
            raise ValueError("material_delta_ref is reserved for ABK_REOPENED")
        return self


class TestReceiptPayload(StrictModel):
    """Test evidence only; this schema intentionally has no closure field."""

    __test__: ClassVar[bool] = False
    receipt_type: Literal["TestReceipt"] = "TestReceipt"
    test_id: NonEmpty
    subject_ref: HashRef
    outcome: NonEmpty
    evidence_refs: tuple[HashRef, ...] = Field(min_length=1)
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)


class ClosureReceiptPayload(StrictModel):
    receipt_type: Literal["ClosureReceipt"] = "ClosureReceipt"
    claim_ref: HashRef
    closure_status: ClosureStatus
    exact_scope: NonEmpty
    authority_ceiling: NonEmpty
    supporting_receipt_refs: tuple[HashRef, ...] = Field(min_length=1)
    open_residual_refs: tuple[HashRef, ...] = Field(default_factory=tuple)
    reopens_closure_ref: HashRef | None = None
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def closure_invariants(self) -> ClosureReceiptPayload:
        if self.closure_status is ClosureStatus.REOPENED:
            if self.reopens_closure_ref is None:
                raise ValueError("REOPENED closure requires the exact prior closure")
        elif self.reopens_closure_ref is not None:
            raise ValueError("reopens_closure_ref is valid only for REOPENED")
        return self


class ResidualReceiptPayload(StrictModel):
    receipt_type: Literal["ResidualReceipt"] = "ResidualReceipt"
    residual_id: HashRef
    operation: ResidualOperation
    resulting_status: ResidualStatus
    scope: NonEmpty
    burden_summary: NonEmpty
    prior_residual_receipt_refs: tuple[HashRef, ...] = Field(default_factory=tuple)
    child_residual_ids: tuple[HashRef, ...] = Field(default_factory=tuple)
    coverage_witness_refs: tuple[HashRef, ...] = Field(default_factory=tuple)
    unallocated_remainder: NonEmpty | None = None
    evidence_refs: tuple[HashRef, ...] = Field(default_factory=tuple)
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def residual_invariants(self) -> ResidualReceiptPayload:
        if self.operation is ResidualOperation.REGISTER:
            if self.prior_residual_receipt_refs:
                raise ValueError("REGISTER cannot cite a prior residual receipt")
            if self.resulting_status is not ResidualStatus.OPEN:
                raise ValueError("REGISTER must result in OPEN")
        else:
            if not self.prior_residual_receipt_refs:
                raise ValueError("residual transition requires prior receipt lineage")
        if self.operation is ResidualOperation.SPLIT:
            if len(self.child_residual_ids) < 2:
                raise ValueError("SPLIT requires at least two child residuals")
            if len(set(self.child_residual_ids)) != len(self.child_residual_ids):
                raise ValueError("SPLIT child residual IDs must be distinct")
            if not self.coverage_witness_refs and self.unallocated_remainder is None:
                raise ValueError(
                    "SPLIT requires a coverage witness or explicit remainder"
                )
        elif self.child_residual_ids:
            raise ValueError("child_residual_ids are valid only for SPLIT")
        expected = {
            ResidualOperation.CARRY: ResidualStatus.OPEN,
            ResidualOperation.SPLIT: ResidualStatus.SUPERSEDED,
            ResidualOperation.PARTIAL_DISCHARGE: ResidualStatus.PARTIALLY_DISCHARGED,
            ResidualOperation.SCOPED_DISCHARGE: ResidualStatus.DISCHARGED_IN_SCOPE,
            ResidualOperation.REOPEN: ResidualStatus.REOPENED,
            ResidualOperation.SUPERSEDE: ResidualStatus.SUPERSEDED,
        }.get(self.operation)
        if expected is not None and self.resulting_status is not expected:
            raise ValueError(f"{self.operation.value} must result in {expected.value}")
        return self


ReceiptPayload: TypeAlias = (
    CutReceiptPayload
    | AccountTransitionReceiptPayload
    | LegacyReceiptRefPayload
    | MaterialDeltaReceiptPayload
    | LifecycleTransitionReceiptPayload
    | TestReceiptPayload
    | ClosureReceiptPayload
    | ResidualReceiptPayload
)


class ReceiptHeader(StrictModel):
    receipt_id: HashRef
    receipt_type: NonEmpty
    schema_id: Literal["A0BK-NATIVE-CANDIDATE"] = "A0BK-NATIVE-CANDIDATE"
    schema_version: Literal["0.1"] = "0.1"
    account_ref: HashRef | Literal["PACKAGE_NA"]
    origin_a0_ref: HashRef | Literal["ORIGIN_SELF"]
    admission_order: int = Field(ge=0)
    payload_hash: HashRef
    prior_links: tuple[HashRef, ...] = Field(default_factory=tuple)
    parent_links: tuple[HashRef, ...] = Field(default_factory=tuple)
    supersedes_links: tuple[HashRef, ...] = Field(default_factory=tuple)
    reopens_links: tuple[HashRef, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def link_invariants(self) -> ReceiptHeader:
        for label, links in (
            ("prior_links", self.prior_links),
            ("parent_links", self.parent_links),
            ("supersedes_links", self.supersedes_links),
            ("reopens_links", self.reopens_links),
        ):
            if len(set(links)) != len(links):
                raise ValueError(f"{label} must not contain duplicate references")
        return self


class TypedReceipt(StrictModel):
    header: ReceiptHeader
    payload: ReceiptPayload = Field(discriminator="receipt_type")

    @model_validator(mode="after")
    def receipt_binding(self) -> TypedReceipt:
        if self.header.receipt_type != self.payload.receipt_type:
            raise ValueError("receipt header type does not match payload type")
        if self.header.payload_hash != sha256_id(self.payload):
            raise ValueError("receipt payload hash mismatch")
        header_basis = self.header.model_dump(mode="python", exclude={"receipt_id"})
        if self.header.receipt_id != sha256_id(header_basis):
            raise ValueError("receipt identity mismatch")
        return self


class AccountHeader(StrictModel):
    account_id: HashRef
    schema_id: Literal["A0BK-NATIVE-CANDIDATE"] = "A0BK-NATIVE-CANDIDATE"
    schema_version: Literal["0.1"] = "0.1"
    account_label: NonEmpty
    operation: AccountOperation
    version: int = Field(ge=1)
    origin_a0_ref: HashRef
    parent_account_ref: HashRef | None = None
    parent_receipt_ref: HashRef | None = None
    immediate_prior_version_ref: HashRef | None = None
    superseded_account_ref: HashRef | None = None
    superseded_receipt_ref: HashRef | None = None
    limitations: tuple[NonEmpty, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def operation_invariants(self) -> AccountHeader:
        paired_parent = (self.parent_account_ref is None) == (
            self.parent_receipt_ref is None
        )
        paired_superseded = (self.superseded_account_ref is None) == (
            self.superseded_receipt_ref is None
        )
        if not paired_parent or not paired_superseded:
            raise ValueError("account and receipt lineage references must be paired")
        if self.operation is AccountOperation.ROOT:
            if self.version != 1 or any(
                item is not None
                for item in (
                    self.parent_account_ref,
                    self.immediate_prior_version_ref,
                    self.superseded_account_ref,
                )
            ):
                raise ValueError("ROOT requires version 1 and no lineage")
        elif self.operation is AccountOperation.CHILD:
            if self.version != 1 or self.parent_account_ref is None:
                raise ValueError("CHILD requires version 1 and one parent pair")
            if self.immediate_prior_version_ref or self.superseded_account_ref:
                raise ValueError("CHILD cannot carry version/successor lineage")
        elif self.operation is AccountOperation.SUCCESSOR:
            if self.version != 1 or self.superseded_account_ref is None:
                raise ValueError("SUCCESSOR requires version 1 and superseded pair")
            if self.parent_account_ref or self.immediate_prior_version_ref:
                raise ValueError("SUCCESSOR cannot carry child/version lineage")
        elif self.operation is AccountOperation.VERSION:
            if self.version < 2 or self.immediate_prior_version_ref is None:
                raise ValueError("VERSION requires an immediate predecessor")
            if self.parent_account_ref or self.superseded_account_ref:
                raise ValueError("VERSION cannot carry child/successor lineage")
        else:
            raise ValueError("APPEND does not create an AccountHeader")
        if self.operation in {
            AccountOperation.ROOT,
            AccountOperation.CHILD,
            AccountOperation.SUCCESSOR,
        }:
            expected = _account_identity(
                account_label=self.account_label,
                operation=self.operation,
                origin_a0_ref=self.origin_a0_ref,
                parent_account_ref=self.parent_account_ref,
                parent_receipt_ref=self.parent_receipt_ref,
                superseded_account_ref=self.superseded_account_ref,
                superseded_receipt_ref=self.superseded_receipt_ref,
            )
            if self.account_id != expected:
                raise ValueError(
                    "new-account identity does not match its opening basis"
                )
        return self


class OpeningBundle(StrictModel):
    account: AccountHeader
    cut_receipt: TypedReceipt

    @model_validator(mode="after")
    def opening_binding(self) -> OpeningBundle:
        if self.account.operation not in {
            AccountOperation.ROOT,
            AccountOperation.CHILD,
            AccountOperation.SUCCESSOR,
        }:
            raise ValueError("opening bundle requires ROOT, CHILD, or SUCCESSOR")
        if self.cut_receipt.header.account_ref != self.account.account_id:
            raise ValueError("opening cut is not bound to the account")
        if self.cut_receipt.header.origin_a0_ref != self.account.origin_a0_ref:
            raise ValueError("opening cut origin mismatch")
        payload = self.cut_receipt.payload
        if not isinstance(payload, CutReceiptPayload):
            raise ValueError("opening bundle requires a CutReceipt")
        if payload.operation is not self.account.operation:
            raise ValueError("opening operation mismatch")
        if payload.cut.cut_ref != self.account.origin_a0_ref:
            raise ValueError("opening payload cut does not match account origin")
        if self.account.operation is AccountOperation.ROOT:
            if any(
                (
                    self.cut_receipt.header.parent_links,
                    self.cut_receipt.header.supersedes_links,
                )
            ):
                raise ValueError("ROOT cut cannot carry parent or successor links")
        elif self.account.operation is AccountOperation.CHILD:
            expected_parent = (
                self.account.parent_account_ref,
                self.account.parent_receipt_ref,
            )
            if self.cut_receipt.header.parent_links != expected_parent:
                raise ValueError("CHILD cut does not match exact parent lineage")
            if self.cut_receipt.header.supersedes_links:
                raise ValueError("CHILD cut cannot carry successor lineage")
        elif self.account.operation is AccountOperation.SUCCESSOR:
            expected_superseded = (
                self.account.superseded_account_ref,
                self.account.superseded_receipt_ref,
            )
            if self.cut_receipt.header.supersedes_links != expected_superseded:
                raise ValueError("SUCCESSOR cut does not match superseded lineage")
            if self.cut_receipt.header.parent_links:
                raise ValueError("SUCCESSOR cut cannot carry parent lineage")
        return self


class VersionOpening(StrictModel):
    account: AccountHeader
    transition_receipt: TypedReceipt

    @model_validator(mode="after")
    def version_binding(self) -> VersionOpening:
        if self.account.operation is not AccountOperation.VERSION:
            raise ValueError("version opening requires VERSION")
        if self.transition_receipt.header.account_ref != self.account.account_id:
            raise ValueError("transition is not bound to the account")
        if self.transition_receipt.header.origin_a0_ref != self.account.origin_a0_ref:
            raise ValueError("transition receipt origin does not match the account")
        payload = self.transition_receipt.payload
        if not isinstance(payload, AccountTransitionReceiptPayload):
            raise ValueError("VERSION requires AccountTransitionReceipt")
        if payload.next_version != self.account.version:
            raise ValueError("transition next_version mismatch")
        if payload.prior_version_ref != self.account.immediate_prior_version_ref:
            raise ValueError("transition prior version mismatch")
        if self.transition_receipt.header.prior_links != (
            self.account.immediate_prior_version_ref,
        ):
            raise ValueError("transition header does not cite exact prior version")
        return self


def _account_identity(
    *,
    account_label: str,
    operation: AccountOperation,
    origin_a0_ref: str,
    parent_account_ref: str | None = None,
    parent_receipt_ref: str | None = None,
    superseded_account_ref: str | None = None,
    superseded_receipt_ref: str | None = None,
) -> str:
    return sha256_id(
        {
            "schema_id": "A0BK-NATIVE-CANDIDATE",
            "schema_version": "0.1",
            "account_label": account_label,
            "opening_operation": operation,
            "origin_a0_ref": origin_a0_ref,
            "parent_account_ref": parent_account_ref,
            "parent_receipt_ref": parent_receipt_ref,
            "superseded_account_ref": superseded_account_ref,
            "superseded_receipt_ref": superseded_receipt_ref,
        }
    )


def make_receipt(
    *,
    payload: ReceiptPayload,
    account_ref: str,
    origin_a0_ref: str,
    admission_order: int,
    prior_links: tuple[str, ...] = (),
    parent_links: tuple[str, ...] = (),
    supersedes_links: tuple[str, ...] = (),
    reopens_links: tuple[str, ...] = (),
) -> TypedReceipt:
    payload_hash = sha256_id(payload)
    basis = {
        "receipt_type": payload.receipt_type,
        "schema_id": "A0BK-NATIVE-CANDIDATE",
        "schema_version": "0.1",
        "account_ref": account_ref,
        "origin_a0_ref": origin_a0_ref,
        "admission_order": admission_order,
        "payload_hash": payload_hash,
        "prior_links": prior_links,
        "parent_links": parent_links,
        "supersedes_links": supersedes_links,
        "reopens_links": reopens_links,
    }
    header = ReceiptHeader(
        receipt_id=sha256_id(basis),
        receipt_type=payload.receipt_type,
        account_ref=account_ref,
        origin_a0_ref=origin_a0_ref,
        admission_order=admission_order,
        payload_hash=payload_hash,
        prior_links=prior_links,
        parent_links=parent_links,
        supersedes_links=supersedes_links,
        reopens_links=reopens_links,
    )
    return TypedReceipt(header=header, payload=payload)


def open_root(
    account_label: str, cut: CutDeclaration, *, limitations: tuple[str, ...]
) -> OpeningBundle:
    account_id = _account_identity(
        account_label=account_label,
        operation=AccountOperation.ROOT,
        origin_a0_ref=cut.cut_ref,
    )
    account = AccountHeader(
        account_id=account_id,
        account_label=account_label,
        operation=AccountOperation.ROOT,
        version=1,
        origin_a0_ref=cut.cut_ref,
        limitations=limitations,
    )
    receipt = make_receipt(
        payload=CutReceiptPayload(cut=cut, operation=AccountOperation.ROOT),
        account_ref=account_id,
        origin_a0_ref=cut.cut_ref,
        admission_order=0,
    )
    return OpeningBundle(account=account, cut_receipt=receipt)


def open_child(
    account_label: str,
    parent_account_ref: str,
    parent_receipt_ref: str,
    cut: CutDeclaration,
    *,
    limitations: tuple[str, ...],
) -> OpeningBundle:
    account_id = _account_identity(
        account_label=account_label,
        operation=AccountOperation.CHILD,
        origin_a0_ref=cut.cut_ref,
        parent_account_ref=parent_account_ref,
        parent_receipt_ref=parent_receipt_ref,
    )
    account = AccountHeader(
        account_id=account_id,
        account_label=account_label,
        operation=AccountOperation.CHILD,
        version=1,
        origin_a0_ref=cut.cut_ref,
        parent_account_ref=parent_account_ref,
        parent_receipt_ref=parent_receipt_ref,
        limitations=limitations,
    )
    receipt = make_receipt(
        payload=CutReceiptPayload(cut=cut, operation=AccountOperation.CHILD),
        account_ref=account_id,
        origin_a0_ref=cut.cut_ref,
        admission_order=0,
        parent_links=(parent_account_ref, parent_receipt_ref),
    )
    return OpeningBundle(account=account, cut_receipt=receipt)


def open_successor(
    account_label: str,
    superseded_account_ref: str,
    superseded_receipt_ref: str,
    cut: CutDeclaration,
    *,
    limitations: tuple[str, ...],
) -> OpeningBundle:
    account_id = _account_identity(
        account_label=account_label,
        operation=AccountOperation.SUCCESSOR,
        origin_a0_ref=cut.cut_ref,
        superseded_account_ref=superseded_account_ref,
        superseded_receipt_ref=superseded_receipt_ref,
    )
    account = AccountHeader(
        account_id=account_id,
        account_label=account_label,
        operation=AccountOperation.SUCCESSOR,
        version=1,
        origin_a0_ref=cut.cut_ref,
        superseded_account_ref=superseded_account_ref,
        superseded_receipt_ref=superseded_receipt_ref,
        limitations=limitations,
    )
    receipt = make_receipt(
        payload=CutReceiptPayload(cut=cut, operation=AccountOperation.SUCCESSOR),
        account_ref=account_id,
        origin_a0_ref=cut.cut_ref,
        admission_order=0,
        supersedes_links=(superseded_account_ref, superseded_receipt_ref),
    )
    return OpeningBundle(account=account, cut_receipt=receipt)


def open_version(
    prior: AccountHeader,
    transition: AccountTransitionReceiptPayload,
    *,
    admission_order: int | None = None,
    limitations: tuple[str, ...] | None = None,
) -> VersionOpening:
    prior_ref = sha256_id(prior)
    if transition.prior_version_ref != prior_ref:
        raise ValueError("VERSION transition does not cite the exact prior header")
    if transition.next_version != prior.version + 1:
        raise ValueError("VERSION must advance exactly one version")
    account = AccountHeader(
        account_id=prior.account_id,
        account_label=prior.account_label,
        operation=AccountOperation.VERSION,
        version=transition.next_version,
        origin_a0_ref=prior.origin_a0_ref,
        immediate_prior_version_ref=prior_ref,
        limitations=prior.limitations if limitations is None else limitations,
    )
    receipt = make_receipt(
        payload=transition,
        account_ref=prior.account_id,
        origin_a0_ref=prior.origin_a0_ref,
        admission_order=(
            transition.next_version - 1 if admission_order is None else admission_order
        ),
        prior_links=(prior_ref,),
    )
    return VersionOpening(account=account, transition_receipt=receipt)


def append_receipt(
    account: AccountHeader,
    payload: ReceiptPayload,
    *,
    admission_order: int,
    prior_links: tuple[str, ...],
    parent_links: tuple[str, ...] = (),
    supersedes_links: tuple[str, ...] = (),
    reopens_links: tuple[str, ...] = (),
) -> TypedReceipt:
    if admission_order < 1:
        raise ValueError("APPEND admission_order must be positive")
    if not prior_links:
        raise ValueError("APPEND requires at least one exact prior receipt link")
    return make_receipt(
        payload=payload,
        account_ref=account.account_id,
        origin_a0_ref=account.origin_a0_ref,
        admission_order=admission_order,
        prior_links=prior_links,
        parent_links=parent_links,
        supersedes_links=supersedes_links,
        reopens_links=reopens_links,
    )


def wrap_legacy_receipt(
    legacy_bytes: bytes,
    *,
    legacy_object_id: str,
    legacy_schema: str,
    source_record: str,
    preserved_scope: str,
    preserved_status: str,
    preserved_authority_ceiling: str,
    limitations: tuple[str, ...],
) -> LegacyReceiptRefPayload:
    """Describe exact legacy bytes without parsing, amending, or uplifting them."""

    return LegacyReceiptRefPayload(
        legacy_object_id=legacy_object_id,
        legacy_schema=legacy_schema,
        exact_content_digest=raw_sha256(legacy_bytes),
        source_record=source_record,
        preserved_scope=preserved_scope,
        preserved_status=preserved_status,
        preserved_authority_ceiling=preserved_authority_ceiling,
        limitations=limitations,
    )


def register_residual(
    *,
    account_ref: str,
    scope: str,
    burden_summary: str,
    evidence_refs: tuple[str, ...],
    limitations: tuple[str, ...],
) -> ResidualReceiptPayload:
    residual_id = sha256_id(
        {
            "account_ref": account_ref,
            "scope": scope,
            "burden_summary": burden_summary,
        }
    )
    return ResidualReceiptPayload(
        residual_id=residual_id,
        operation=ResidualOperation.REGISTER,
        resulting_status=ResidualStatus.OPEN,
        scope=scope,
        burden_summary=burden_summary,
        evidence_refs=evidence_refs,
        limitations=limitations,
    )


def transition_residual(
    prior: ResidualReceiptPayload,
    *,
    operation: ResidualOperation,
    prior_receipt_ref: str,
    resulting_status: ResidualStatus,
    burden_summary: str | None = None,
    child_residual_ids: tuple[str, ...] = (),
    coverage_witness_refs: tuple[str, ...] = (),
    unallocated_remainder: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    limitations: tuple[str, ...] | None = None,
) -> ResidualReceiptPayload:
    if operation is ResidualOperation.REGISTER:
        raise ValueError("use register_residual for REGISTER")
    return ResidualReceiptPayload(
        residual_id=prior.residual_id,
        operation=operation,
        resulting_status=resulting_status,
        scope=prior.scope,
        burden_summary=(
            prior.burden_summary if burden_summary is None else burden_summary
        ),
        prior_residual_receipt_refs=(prior_receipt_ref,),
        child_residual_ids=child_residual_ids,
        coverage_witness_refs=coverage_witness_refs,
        unallocated_remainder=unallocated_remainder,
        evidence_refs=evidence_refs,
        limitations=prior.limitations if limitations is None else limitations,
    )


__all__ = [
    "ABKLifecycle",
    "AccountHeader",
    "AccountTransitionReceiptPayload",
    "ClosureReceiptPayload",
    "ClosureStatus",
    "CutDeclaration",
    "CutReceiptPayload",
    "LegacyReceiptRefPayload",
    "LifecycleTransitionReceiptPayload",
    "MaterialDeltaReceiptPayload",
    "OpeningBundle",
    "ReceiptHeader",
    "ResidualOperation",
    "ResidualReceiptPayload",
    "ResidualStatus",
    "TestReceiptPayload",
    "TypedReceipt",
    "VersionOpening",
    "append_receipt",
    "make_receipt",
    "open_child",
    "open_root",
    "open_successor",
    "open_version",
    "register_residual",
    "transition_residual",
    "wrap_legacy_receipt",
]
