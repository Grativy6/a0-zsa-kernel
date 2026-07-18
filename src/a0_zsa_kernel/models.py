from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AttemptOutcome,
    CheckResult,
    ExpirySubject,
    FailureCategory,
    LifecycleStatus,
    Operation,
)

DECIMAL_RE = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d{1,6})?$")


def _fixed_decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or not DECIMAL_RE.fullmatch(value):
        raise ValueError("fixed decimal must be a non-negative JSON string with at most six decimal places")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("fixed decimal must be finite")
    return result


FixedDecimal = Annotated[Decimal, BeforeValidator(_fixed_decimal)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc_seconds(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    utc = value.astimezone(timezone.utc)
    if utc.microsecond:
        raise ValueError("timestamp must use whole-second precision")
    return utc


class CandidateSnapshot(StrictModel):
    candidate_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    content: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None = None
    content_hash: str

    _created_utc = field_validator("created_at", mode="after")(_utc_seconds)
    _expires_utc = field_validator("expires_at", mode="after")(
        lambda value: None if value is None else _utc_seconds(value)
    )


class CurrentState(StrictModel):
    candidate_id: str
    status: LifecycleStatus
    candidate_content_hash: str
    evidence_manifest_hash: str | None = None
    last_receipt_id: str | None = None


class RequestedTransition(StrictModel):
    from_status: LifecycleStatus
    to_status: LifecycleStatus
    reason: str = Field(min_length=1)


class ObservationSource(StrictModel):
    source_id: str
    source_type: str


class Observation(StrictModel):
    observation_id: str
    kind: str
    value: dict[str, Any]
    source: ObservationSource
    observed_at: datetime
    evidence_strength: FixedDecimal

    _observed_utc = field_validator("observed_at", mode="after")(_utc_seconds)

    @field_validator("evidence_strength")
    @classmethod
    def strength_range(cls, value: Decimal) -> Decimal:
        if value > Decimal("1"):
            raise ValueError("evidence_strength must be between 0 and 1")
        return value


class Weighting(StrictModel):
    rule_id: str
    factors: dict[str, FixedDecimal]
    result: FixedDecimal
    hard_vetoes: list[str] = Field(default_factory=list)


class Measurement(StrictModel):
    measurement_id: str
    purpose: str
    method: str
    observation_refs: list[str]
    result: dict[str, Any]
    uncertainty: dict[str, Any]
    unresolved_burdens: list[str] = Field(default_factory=list)


class AuthorityContext(StrictModel):
    actor_id: str
    actor_type: str
    lineage: list[str]
    allowed_actions: list[str]
    allowed_targets: list[str]
    valid_from: datetime
    valid_until: datetime
    scope: str
    control_mode: str
    credential_ref: str
    rule_adoption_authority_refs: list[str] = Field(default_factory=list)

    _valid_from_utc = field_validator("valid_from", mode="after")(_utc_seconds)
    _valid_until_utc = field_validator("valid_until", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def valid_interval(self) -> "AuthorityContext":
        if self.valid_from >= self.valid_until:
            raise ValueError("authority valid_from must precede valid_until")
        return self


class RuleGovernance(StrictModel):
    author: str
    adopter: str
    scope: str
    effective_from: datetime
    effective_until: datetime
    rule_hash: str
    authority_reference: str

    _effective_from_utc = field_validator("effective_from", mode="after")(_utc_seconds)
    _effective_until_utc = field_validator("effective_until", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def effective_interval(self) -> "RuleGovernance":
        if self.effective_from >= self.effective_until:
            raise ValueError("rule effective_from must precede effective_until")
        return self


class TransitionSpec(StrictModel):
    from_status: LifecycleStatus
    to_status: LifecycleStatus


class AdmissibilityRule(StrictModel):
    rule_id: str
    rule_version: str
    governance: RuleGovernance
    permitted_transition: TransitionSpec
    required_observation_kinds: list[str] = Field(default_factory=list)
    minimum_weights: dict[str, FixedDecimal] = Field(default_factory=dict)
    maximum_weights: dict[str, FixedDecimal] = Field(default_factory=dict)
    required_authority_action: str
    allowed_unresolved_burdens: list[str] = Field(default_factory=list)
    veto_conditions: list[str] = Field(default_factory=list)


class FailureRecord(StrictModel):
    failure_id: str
    category: FailureCategory
    code: str
    description: str
    correctable: bool
    occurred_receipt_id: str


class MaterialDelta(StrictModel):
    category: FailureCategory
    resolves_failure_ids: list[str] = Field(min_length=1)
    field: str
    before_hash: str
    after_hash: str
    description: str

    @model_validator(mode="after")
    def hashes_differ(self) -> "MaterialDelta":
        if self.before_hash == self.after_hash:
            raise ValueError("material delta must change the referenced value")
        return self


class ReopeningRequest(StrictModel):
    prior_candidate_id: str
    prior_candidate_content_hash: str
    prior_status: LifecycleStatus
    prior_receipt_id: str
    failures: list[FailureRecord]
    material_deltas: list[MaterialDelta]
    declared_reopening_condition: str


class ExpiryDeclaration(StrictModel):
    subject: ExpirySubject
    window_id: str
    explanation: str


class TransitionProfile(StrictModel):
    profile_id: str
    allow_unresolved_expiry: bool = False


class TraceContext(StrictModel):
    previous_receipt_id: str | None = None
    parent_candidate_id: str | None = None
    inherited_receipt_ids: list[str] = Field(default_factory=list)
    failures: list[FailureRecord] = Field(default_factory=list)
    reopening: ReopeningRequest | None = None


class TransitionPacket(StrictModel):
    schema_version: Literal["0.1"]
    packet_id: str
    operation: Operation
    evaluation_time: datetime
    candidate: CandidateSnapshot
    current_state: CurrentState
    requested_transition: RequestedTransition
    observations: list[Observation] = Field(default_factory=list)
    weighting: Weighting | None = None
    measurement: Measurement | None = None
    authority: AuthorityContext | None = None
    admissibility_rule: AdmissibilityRule | None = None
    transition_profile: TransitionProfile = Field(
        default_factory=lambda: TransitionProfile(profile_id="BASELINE", allow_unresolved_expiry=False)
    )
    expiry: ExpiryDeclaration | None = None
    trace: TraceContext = Field(default_factory=TraceContext)

    _evaluation_utc = field_validator("evaluation_time", mode="after")(_utc_seconds)


class CheckRecord(StrictModel):
    check_id: str
    result: CheckResult
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceManifestEntry(StrictModel):
    observation_id: str
    observation_hash: str


class ReplayAudit(StrictModel):
    original_receipt_id: str
    original_decision_id: str
    receipt_matches: bool
    decision_matches: bool


class AttemptReceipt(StrictModel):
    schema_version: Literal["0.1"] = "0.1"
    receipt_id: str
    decision_id: str
    packet_id: str | None
    packet_hash: str
    attempt_outcome: AttemptOutcome
    attempted_transition: RequestedTransition | None
    prior_lifecycle_status: LifecycleStatus | None
    resulting_lifecycle_status: LifecycleStatus | None
    lifecycle_changed: bool
    source_record_unchanged: bool = True
    control_modes: list[str] = Field(default_factory=list)
    checks: list[CheckRecord] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    candidate_snapshot_hash: str | None = None
    evidence_manifest: list[EvidenceManifestEntry] = Field(default_factory=list)
    authority_snapshot_hash: str | None = None
    admissibility_rule_hash: str | None = None
    unresolved_burdens: list[str] = Field(default_factory=list)
    reopening_conditions: list[str] = Field(default_factory=list)
    retained_failures: list[FailureRecord] = Field(default_factory=list)
    resolved_failures: list[FailureRecord] = Field(default_factory=list)
    replay_audit: ReplayAudit | None = None
    non_claims: list[str] = Field(default_factory=list)
