"""Typed proposal, control, guard, and route models for advisory Strongwiz use."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.main import BaseModel

HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"
DECIMAL_RE = re.compile(r"^(?:0|1)(?:\.\d{1,6})?$")
HashRef = Annotated[str, Field(pattern=HASH_PATTERN)]


def _unit_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and DECIMAL_RE.fullmatch(value):
        result = Decimal(value)
    else:
        raise ValueError("unit decimal must be a JSON string from 0 through 1")
    if not result.is_finite() or result < 0 or result > 1:
        raise ValueError("unit decimal must be finite and between 0 and 1")
    return result


UnitDecimal = Annotated[Decimal, BeforeValidator(_unit_decimal)]


def _utc_seconds(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    utc = value.astimezone(UTC)
    if utc.microsecond:
        raise ValueError("timestamp must use whole-second precision")
    return utc


def _unique(values: list[Any], label: str) -> list[Any]:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} values must be unique")
    return values


def _validate_json_tree(value: Any, *, path: str = "$") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_tree(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{path} contains a non-string object name")
            _validate_json_tree(item, path=f"{path}.{key}")
        return
    raise ValueError(
        f"{path} contains forbidden programmatic JSON type {type(value).__name__}"
    )


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    def a0bk_canonical_value(self) -> dict[str, Any]:
        # Pydantic's model_copy(update=...) intentionally skips validation.
        # Canonical identity is a trust boundary, so round-trip through the
        # strict schema before any JSON-mode coercion can conceal a bad value.
        validated = type(self).model_validate(self.model_dump(mode="python"))
        return validated.model_dump(mode="json", exclude_none=False)


class AccountOperation(StrEnum):
    ROOT = "ROOT"
    APPEND = "APPEND"
    CHILD = "CHILD"
    VERSION = "VERSION"
    SUCCESSOR = "SUCCESSOR"


class RouteDisposition(StrEnum):
    ADMIT = "ADMIT"
    HOLD = "HOLD"
    REQUEST_WITNESS = "REQUEST_WITNESS"
    REJECT = "REJECT"
    REOPEN = "REOPEN"


class RouterStage(StrEnum):
    W0_FREEZE = "W0_FREEZE"
    W1_WITNESS = "W1_WITNESS"
    W2_HARD_GUARDS = "W2_HARD_GUARDS"
    W3_BOUNDARY = "W3_BOUNDARY"
    W4_DIAGNOSTICS = "W4_DIAGNOSTICS"
    W5_ROUTE = "W5_ROUTE"
    W6_RETURN = "W6_RETURN"


class GuardVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConsequenceClass(StrEnum):
    REVERSIBLE = "REVERSIBLE"
    RESOURCE_COMMITMENT = "RESOURCE_COMMITMENT"
    LIFE_OR_RESET = "LIFE_OR_RESET"
    IRREVERSIBLE = "IRREVERSIBLE"
    EXTERNAL = "EXTERNAL"


class DecisionEffect(StrEnum):
    PLAN = "PLAN"
    RISK = "RISK"
    CANDIDATE = "CANDIDATE"
    EXPERIMENT = "EXPERIMENT"
    RESOURCE = "RESOURCE"
    ACCESS = "ACCESS"
    HAZARD = "HAZARD"
    MOVEMENT = "MOVEMENT"


class RouterMode(StrEnum):
    SHADOW_ONLY = "SHADOW_ONLY"


class GuardId(StrEnum):
    IDENTITY = "IDENTITY"
    WITNESS = "WITNESS"
    SCOPE = "SCOPE"
    TRACE = "TRACE"
    AUTHORITY = "AUTHORITY"
    CONSEQUENCE = "CONSEQUENCE"
    RESOURCE = "RESOURCE"
    REENTRY = "REENTRY"


class CandidateProposal(StrictModel):
    candidate_id: str = Field(min_length=1)
    proposed_rank: int = Field(ge=0)
    action_id: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    predicted_consequence: dict[str, Any]
    meaningful_distinction: str = Field(min_length=1)
    decision_effects: list[DecisionEffect] = Field(min_length=1)
    evidence_refs: list[HashRef] = Field(min_length=1)
    conflicting_evidence_refs: list[HashRef] = Field(default_factory=list)
    residual_refs: list[HashRef] = Field(default_factory=list)
    material_delta_refs: list[HashRef] = Field(default_factory=list)
    reopens_account_ref: HashRef | None = None
    uncertainty: UnitDecimal
    metrics: dict[str, UnitDecimal] = Field(default_factory=dict)
    action_cost: int = Field(ge=0)
    life_cost: int = Field(ge=0)
    reversible: bool
    consequence_class: ConsequenceClass
    summary_reason: str = Field(min_length=1)

    @field_validator("predicted_consequence", mode="before")
    @classmethod
    def consequence_is_unambiguous_json(cls, value: Any) -> Any:
        _validate_json_tree(value, path="$.predicted_consequence")
        return value

    @model_validator(mode="after")
    def candidate_invariants(self) -> CandidateProposal:
        _unique(self.decision_effects, "decision_effects")
        _unique(self.evidence_refs, "evidence_refs")
        _unique(self.conflicting_evidence_refs, "conflicting_evidence_refs")
        _unique(self.residual_refs, "residual_refs")
        _unique(self.material_delta_refs, "material_delta_refs")
        if self.reopens_account_ref is not None and not self.material_delta_refs:
            raise ValueError(
                "a reopening candidate requires a material delta reference"
            )
        return self


class ProposalPacket(StrictModel):
    schema_version: Literal["0.1"] = "0.1"
    packet_id: str = Field(min_length=1)
    root_goal: str = Field(min_length=1)
    scoped_goal: str = Field(min_length=1)
    active_account_ref: HashRef
    active_account_version: int = Field(ge=1)
    observation_ref: HashRef
    observation_hash: HashRef
    action_space: list[str] = Field(min_length=1)
    candidates: list[CandidateProposal] = Field(min_length=1)
    prior_receipt_refs: list[HashRef] = Field(default_factory=list)
    candidate_generator_ref: HashRef
    generated_at: datetime

    _generated_utc = field_validator("generated_at", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def packet_invariants(self) -> ProposalPacket:
        _unique(self.action_space, "action_space")
        _unique(self.prior_receipt_refs, "prior_receipt_refs")
        _unique([item.candidate_id for item in self.candidates], "candidate_id")
        _unique([item.proposed_rank for item in self.candidates], "proposed_rank")
        return self


class BudgetSnapshot(StrictModel):
    remaining_actions: int = Field(ge=0)
    remaining_lives: int = Field(ge=0)
    remaining_wall_clock_ms: int = Field(ge=0)


class GrantSnapshot(StrictModel):
    grant_id: HashRef
    issuer_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    allowed_action_ids: list[str] = Field(min_length=1)
    allowed_target_refs: list[str] = Field(min_length=1)
    valid_from: datetime
    valid_until: datetime
    revoked: bool = False
    nonce_ref: HashRef
    authorizes_external_effects: bool = False
    trust_root_ref: HashRef

    _from_utc = field_validator("valid_from", mode="after")(_utc_seconds)
    _until_utc = field_validator("valid_until", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def grant_invariants(self) -> GrantSnapshot:
        if self.valid_from >= self.valid_until:
            raise ValueError("grant valid_from must precede valid_until")
        _unique(self.allowed_action_ids, "allowed_action_ids")
        _unique(self.allowed_target_refs, "allowed_target_refs")
        return self


class GuardDefinition(StrictModel):
    guard_id: GuardId
    source_ref: HashRef
    source_version: str = Field(min_length=1)
    authority_ceiling: str = Field(min_length=1)


class DiagnosticDimension(StrictModel):
    name: str = Field(min_length=1)
    weight: UnitDecimal
    direction: Literal["MAXIMIZE"] = "MAXIMIZE"
    missing_value_rule: Literal["INELIGIBLE"] = "INELIGIBLE"


class DiagnosticProfile(StrictModel):
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    decision_not_permitted: str = Field(min_length=1)
    dimensions: list[DiagnosticDimension] = Field(min_length=1)
    aggregation: Literal["WEIGHTED_SUM"] = "WEIGHTED_SUM"
    sensitivity_ref: HashRef
    calibration_ref: HashRef
    limitations: list[str] = Field(min_length=1)
    expires_at: datetime
    hard_guard_override_forbidden: Literal[True] = True

    _expires_utc = field_validator("expires_at", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def diagnostic_invariants(self) -> DiagnosticProfile:
        _unique([item.name for item in self.dimensions], "diagnostic dimension")
        return self


class RouterPolicy(StrictModel):
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    source_ref: HashRef
    scope: str = Field(min_length=1)
    mode: Literal[RouterMode.SHADOW_ONLY] = RouterMode.SHADOW_ONLY
    guards: list[GuardDefinition] = Field(min_length=8, max_length=8)
    diagnostic: DiagnosticProfile | None = None
    allow_external_proposals: bool = False
    non_claims: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def policy_invariants(self) -> RouterPolicy:
        ids = [item.guard_id for item in self.guards]
        _unique(ids, "guard_id")
        if set(ids) != set(GuardId):
            raise ValueError("policy must declare every hard guard exactly once")
        return self


class ControlSnapshot(StrictModel):
    control_id: HashRef
    evaluated_at: datetime
    active_account_ref: HashRef
    active_account_version: int = Field(ge=1)
    current_observation_hash: HashRef
    available_evidence_refs: list[HashRef] = Field(default_factory=list)
    available_trace_refs: list[HashRef] = Field(default_factory=list)
    active_residual_refs: list[HashRef] = Field(default_factory=list)
    budget: BudgetSnapshot
    grant: GrantSnapshot
    serial_token_ref: HashRef
    consumed_serial_token_refs: list[HashRef] = Field(default_factory=list)
    policy: RouterPolicy

    _evaluated_utc = field_validator("evaluated_at", mode="after")(_utc_seconds)

    @model_validator(mode="after")
    def control_invariants(self) -> ControlSnapshot:
        _unique(self.available_evidence_refs, "available_evidence_refs")
        _unique(self.available_trace_refs, "available_trace_refs")
        _unique(self.active_residual_refs, "active_residual_refs")
        _unique(self.consumed_serial_token_refs, "consumed_serial_token_refs")
        return self


class RoutingRequest(StrictModel):
    schema_version: Literal["0.1"] = "0.1"
    proposal: ProposalPacket
    control: ControlSnapshot


class GuardResult(StrictModel):
    candidate_id: str
    guard_id: GuardId
    verdict: GuardVerdict
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[HashRef] = Field(default_factory=list)


class StageResult(StrictModel):
    stage: RouterStage
    verdict: GuardVerdict
    reason_codes: list[str] = Field(default_factory=list)


class CandidateEvaluation(StrictModel):
    candidate_id: str
    eligible: bool
    diagnostic_score: Decimal | None = None
    guard_results: list[GuardResult]


class RouteDecision(StrictModel):
    schema_version: Literal["0.1"] = "0.1"
    decision_id: HashRef
    packet_id: str | None
    proposal_hash: HashRef
    control_hash: HashRef | None
    policy_hash: HashRef | None
    route: RouteDisposition
    selected_candidate_id: str | None
    stages: list[StageResult]
    candidates: list[CandidateEvaluation]
    reason_codes: list[str]
    required_next_receipts: list[str]
    mode: RouterMode = RouterMode.SHADOW_ONLY
    nonexecution_marker: Literal[True] = True
    authority: Literal["NONE"] = "NONE"
    effect: Literal["NONE"] = "NONE"
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def decision_identity(self) -> RouteDecision:
        from .canonical import sha256_id

        basis = self.model_dump(mode="json", exclude={"decision_id"})
        if self.decision_id != sha256_id(basis):
            raise ValueError("route decision identity mismatch")
        return self


__all__ = [
    "AccountOperation",
    "BudgetSnapshot",
    "CandidateEvaluation",
    "CandidateProposal",
    "ConsequenceClass",
    "ControlSnapshot",
    "DecisionEffect",
    "DiagnosticDimension",
    "DiagnosticProfile",
    "GrantSnapshot",
    "GuardDefinition",
    "GuardId",
    "GuardResult",
    "GuardVerdict",
    "HashRef",
    "ProposalPacket",
    "RouteDecision",
    "RouteDisposition",
    "RouterMode",
    "RouterPolicy",
    "RouterStage",
    "RoutingRequest",
    "StageResult",
    "StrictModel",
    "UnitDecimal",
]
