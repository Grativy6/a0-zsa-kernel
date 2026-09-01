"""Deterministic W0-W6 shadow routing for Strongwiz proposal packets.

The evaluator is pure: it selects one advisory route and never invokes an
executor, network service, connector, credential, or environment action.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from .canonical import (
    CanonicalJSONError,
    canonical_bytes,
    load_bytes_strict,
    raw_sha256,
    sha256_id,
)
from .models import (
    CandidateEvaluation,
    CandidateProposal,
    ConsequenceClass,
    ControlSnapshot,
    GuardId,
    GuardResult,
    GuardVerdict,
    ProposalPacket,
    RouteDecision,
    RouteDisposition,
    RouterStage,
    RoutingRequest,
    StageResult,
)

LIMITATIONS = [
    "Selected project profile; not complete A0BK, PAL, ZSA, FBT, PECAN, "
    "or A12 conformance.",
    "The supplied control snapshot is checked internally but is not "
    "authenticated as real-world authority.",
    "The result is advisory, has no execution authority, and performs no "
    "external action.",
]


def _guard(
    candidate: CandidateProposal,
    guard_id: GuardId,
    verdict: GuardVerdict,
    *reason_codes: str,
    evidence_refs: Iterable[str] = (),
) -> GuardResult:
    return GuardResult(
        candidate_id=candidate.candidate_id,
        guard_id=guard_id,
        verdict=verdict,
        reason_codes=list(reason_codes),
        evidence_refs=list(evidence_refs),
    )


def _identity_guard(
    proposal: ProposalPacket, control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    reasons: list[str] = []
    if proposal.active_account_ref != control.active_account_ref:
        reasons.append("ACCOUNT_BINDING_MISMATCH")
    if proposal.active_account_version != control.active_account_version:
        reasons.append("ACCOUNT_VERSION_MISMATCH")
    if proposal.observation_hash != control.current_observation_hash:
        reasons.append("OBSERVATION_BINDING_MISMATCH")
    return _guard(
        candidate,
        GuardId.IDENTITY,
        GuardVerdict.PASS if not reasons else GuardVerdict.FAIL,
        *(reasons or ["IDENTITY_BOUND"]),
        evidence_refs=(proposal.active_account_ref, proposal.observation_hash),
    )


def _witness_guard(
    control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    required = set(candidate.evidence_refs)
    required.update(candidate.conflicting_evidence_refs)
    required.update(candidate.material_delta_refs)
    available = set(control.available_evidence_refs)
    missing = sorted(required - available)
    if missing:
        return _guard(
            candidate,
            GuardId.WITNESS,
            GuardVerdict.UNRESOLVED,
            "EVIDENCE_UNAVAILABLE",
            evidence_refs=missing,
        )
    return _guard(
        candidate,
        GuardId.WITNESS,
        GuardVerdict.PASS,
        "EVIDENCE_AVAILABLE",
        evidence_refs=sorted(required),
    )


def _scope_guard(
    proposal: ProposalPacket, control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    reasons: list[str] = []
    grant = control.grant
    if candidate.action_id not in proposal.action_space:
        reasons.append("ACTION_OUTSIDE_OBSERVED_SPACE")
    if candidate.action_id not in grant.allowed_action_ids:
        reasons.append("ACTION_OUTSIDE_GRANT")
    if candidate.target_ref not in grant.allowed_target_refs:
        reasons.append("TARGET_OUTSIDE_GRANT")
    if grant.scope != control.policy.scope:
        reasons.append("GRANT_POLICY_SCOPE_MISMATCH")
    return _guard(
        candidate,
        GuardId.SCOPE,
        GuardVerdict.PASS if not reasons else GuardVerdict.FAIL,
        *(reasons or ["SCOPE_BOUND"]),
    )


def _trace_guard(
    proposal: ProposalPacket, control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    missing_trace = sorted(
        set(proposal.prior_receipt_refs) - set(control.available_trace_refs)
    )
    missing_residual = sorted(
        set(candidate.residual_refs) - set(control.active_residual_refs)
    )
    if missing_trace or missing_residual:
        codes: list[str] = []
        if missing_trace:
            codes.append("PRIOR_TRACE_UNAVAILABLE")
        if missing_residual:
            codes.append("RESIDUAL_NOT_ACTIVE")
        return _guard(
            candidate,
            GuardId.TRACE,
            GuardVerdict.UNRESOLVED,
            *codes,
            evidence_refs=missing_trace + missing_residual,
        )
    return _guard(
        candidate,
        GuardId.TRACE,
        GuardVerdict.PASS,
        "TRACE_BOUND",
        evidence_refs=proposal.prior_receipt_refs + candidate.residual_refs,
    )


def _authority_guard(
    control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    grant = control.grant
    reasons: list[str] = []
    if grant.revoked:
        reasons.append("GRANT_REVOKED")
    if control.evaluated_at < grant.valid_from:
        reasons.append("GRANT_NOT_YET_VALID")
    if control.evaluated_at >= grant.valid_until:
        reasons.append("GRANT_EXPIRED")
    if grant.nonce_ref != control.serial_token_ref:
        reasons.append("GRANT_TOKEN_BINDING_MISMATCH")
    if not grant.actor_id or not grant.issuer_id:
        reasons.append("DECLARED_ACTOR_OR_ISSUER_MISSING")
    return _guard(
        candidate,
        GuardId.AUTHORITY,
        GuardVerdict.PASS if not reasons else GuardVerdict.FAIL,
        *(reasons or ["DECLARED_GRANT_CURRENT"]),
        evidence_refs=(grant.grant_id, grant.trust_root_ref),
    )


def _consequence_guard(
    control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    reasons: list[str] = []
    if candidate.reversible and candidate.consequence_class in {
        ConsequenceClass.IRREVERSIBLE,
        ConsequenceClass.EXTERNAL,
    }:
        reasons.append("REVERSIBILITY_CONTRADICTS_CONSEQUENCE_CLASS")
    if candidate.consequence_class is ConsequenceClass.EXTERNAL:
        if not control.policy.allow_external_proposals:
            reasons.append("EXTERNAL_PROPOSALS_DISABLED")
        if not control.grant.authorizes_external_effects:
            reasons.append("EXTERNAL_EFFECT_NOT_DECLARED_IN_GRANT")
    if candidate.consequence_class is ConsequenceClass.IRREVERSIBLE:
        reasons.append("IRREVERSIBLE_REQUIRES_SEPARATE_CROSSING")
    if reasons:
        return _guard(
            candidate,
            GuardId.CONSEQUENCE,
            GuardVerdict.UNRESOLVED,
            *reasons,
        )
    return _guard(
        candidate,
        GuardId.CONSEQUENCE,
        GuardVerdict.PASS,
        "CONSEQUENCE_WITHIN_SHADOW_PROFILE",
    )


def _resource_guard(
    control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    reasons: list[str] = []
    if candidate.action_cost > control.budget.remaining_actions:
        reasons.append("ACTION_BUDGET_EXCEEDED")
    if candidate.life_cost > control.budget.remaining_lives:
        reasons.append("LIFE_BUDGET_EXCEEDED")
    if control.budget.remaining_wall_clock_ms <= 0:
        reasons.append("WALL_CLOCK_BUDGET_EXHAUSTED")
    return _guard(
        candidate,
        GuardId.RESOURCE,
        GuardVerdict.PASS if not reasons else GuardVerdict.FAIL,
        *(reasons or ["DECLARED_RESOURCE_BUDGET_AVAILABLE"]),
    )


def _reentry_guard(
    control: ControlSnapshot, candidate: CandidateProposal
) -> GuardResult:
    if control.serial_token_ref in control.consumed_serial_token_refs:
        return _guard(
            candidate,
            GuardId.REENTRY,
            GuardVerdict.FAIL,
            "SERIAL_TOKEN_ALREADY_CONSUMED",
            evidence_refs=(control.serial_token_ref,),
        )
    return _guard(
        candidate,
        GuardId.REENTRY,
        GuardVerdict.PASS,
        "SERIAL_TOKEN_LIVE",
        evidence_refs=(control.serial_token_ref,),
    )


def _evaluate_candidate(
    proposal: ProposalPacket, control: ControlSnapshot, candidate: CandidateProposal
) -> CandidateEvaluation:
    guards = [
        _identity_guard(proposal, control, candidate),
        _witness_guard(control, candidate),
        _scope_guard(proposal, control, candidate),
        _trace_guard(proposal, control, candidate),
        _authority_guard(control, candidate),
        _consequence_guard(control, candidate),
        _resource_guard(control, candidate),
        _reentry_guard(control, candidate),
    ]
    eligible = all(
        item.verdict in {GuardVerdict.PASS, GuardVerdict.NOT_APPLICABLE}
        for item in guards
    )
    score: Decimal | None = None
    diagnostic = control.policy.diagnostic
    if eligible and diagnostic is not None:
        if control.evaluated_at >= diagnostic.expires_at:
            eligible = False
        else:
            required = {item.name for item in diagnostic.dimensions}
            if not required.issubset(candidate.metrics):
                eligible = False
            else:
                score = sum(
                    (
                        candidate.metrics[item.name] * item.weight
                        for item in diagnostic.dimensions
                    ),
                    Decimal("0"),
                )
    return CandidateEvaluation(
        candidate_id=candidate.candidate_id,
        eligible=eligible,
        diagnostic_score=score,
        guard_results=guards,
    )


def _select(
    proposal: ProposalPacket,
    control: ControlSnapshot,
    evaluations: list[CandidateEvaluation],
) -> CandidateProposal | None:
    eligible = [item for item in evaluations if item.eligible]
    if not eligible:
        return None
    by_id = {item.candidate_id: item for item in proposal.candidates}
    if control.policy.diagnostic is None:
        chosen = min(
            eligible,
            key=lambda item: (
                by_id[item.candidate_id].proposed_rank,
                item.candidate_id,
            ),
        )
    else:
        chosen = min(
            eligible,
            key=lambda item: (
                -(item.diagnostic_score or Decimal("0")),
                by_id[item.candidate_id].proposed_rank,
                item.candidate_id,
            ),
        )
    return by_id[chosen.candidate_id]


def _unselected_route(
    evaluations: list[CandidateEvaluation],
) -> tuple[RouteDisposition, list[str], list[str]]:
    results = [guard for item in evaluations for guard in item.guard_results]
    failed = {item.guard_id for item in results if item.verdict is GuardVerdict.FAIL}
    unresolved = {
        item.guard_id for item in results if item.verdict is GuardVerdict.UNRESOLVED
    }
    reason_codes = sorted(
        {code for item in results for code in item.reason_codes if code}
    )
    if failed & {GuardId.IDENTITY, GuardId.SCOPE, GuardId.AUTHORITY, GuardId.REENTRY}:
        return RouteDisposition.REJECT, reason_codes, []
    if unresolved & {GuardId.WITNESS, GuardId.TRACE}:
        return (
            RouteDisposition.REQUEST_WITNESS,
            reason_codes,
            ["EvidenceReceipt", "TraceReceipt"],
        )
    if failed & {GuardId.RESOURCE} or unresolved & {GuardId.CONSEQUENCE}:
        return RouteDisposition.HOLD, reason_codes, ["UpdatedControlSnapshot"]
    return RouteDisposition.REJECT, reason_codes or ["NO_ELIGIBLE_CANDIDATE"], []


def _aggregate_verdict(
    evaluations: list[CandidateEvaluation], guard_ids: set[GuardId]
) -> GuardVerdict:
    results = [
        result
        for item in evaluations
        for result in item.guard_results
        if result.guard_id in guard_ids
    ]
    if any(item.verdict is GuardVerdict.PASS for item in results):
        return GuardVerdict.PASS
    if any(item.verdict is GuardVerdict.UNRESOLVED for item in results):
        return GuardVerdict.UNRESOLVED
    if any(item.verdict is GuardVerdict.FAIL for item in results):
        return GuardVerdict.FAIL
    return GuardVerdict.NOT_APPLICABLE


def _finalize_decision(values: dict[str, Any]) -> RouteDecision:
    decision_id = sha256_id(values)
    return RouteDecision(decision_id=decision_id, **values)


def evaluate_route(request: RoutingRequest) -> RouteDecision:
    """Evaluate a validated request and return exactly one advisory decision."""

    proposal = request.proposal
    control = request.control
    proposal_hash = sha256_id(proposal)
    control_hash = sha256_id(control)
    policy_hash = sha256_id(control.policy)
    evaluations = [
        _evaluate_candidate(proposal, control, candidate)
        for candidate in proposal.candidates
    ]
    selected = _select(proposal, control, evaluations)
    required: list[str] = []
    if selected is not None:
        if selected.reopens_account_ref is not None:
            route = RouteDisposition.REOPEN
            reasons = ["MATERIAL_DELTA_REOPENING_SELECTED"]
            required = ["LifecycleTransitionReceipt", "MaterialDeltaReceipt"]
        else:
            route = RouteDisposition.ADMIT
            reasons = ["SHADOW_CANDIDATE_ELIGIBLE"]
            required = ["RouteReceipt"]
    else:
        route, reasons, required = _unselected_route(evaluations)

    witness_verdict = _aggregate_verdict(evaluations, {GuardId.WITNESS, GuardId.TRACE})
    hard_verdict = (
        GuardVerdict.PASS
        if selected is not None
        else _aggregate_verdict(evaluations, set(GuardId))
    )
    boundary_verdict = _aggregate_verdict(evaluations, {GuardId.CONSEQUENCE})
    stages = [
        StageResult(
            stage=RouterStage.W0_FREEZE,
            verdict=_aggregate_verdict(evaluations, {GuardId.IDENTITY}),
            reason_codes=["REQUEST_HASHES_BOUND"],
        ),
        StageResult(
            stage=RouterStage.W1_WITNESS,
            verdict=witness_verdict,
            reason_codes=["WITNESS_APERTURE_EVALUATED"],
        ),
        StageResult(
            stage=RouterStage.W2_HARD_GUARDS,
            verdict=hard_verdict,
            reason_codes=["ALL_DECLARED_HARD_GUARDS_EVALUATED"],
        ),
        StageResult(
            stage=RouterStage.W3_BOUNDARY,
            verdict=boundary_verdict,
            reason_codes=["SHADOW_BOUNDARY_ONLY"],
        ),
        StageResult(
            stage=RouterStage.W4_DIAGNOSTICS,
            verdict=(
                GuardVerdict.NOT_APPLICABLE
                if control.policy.diagnostic is None
                else (GuardVerdict.PASS if selected is not None else GuardVerdict.FAIL)
            ),
            reason_codes=[
                "DIAGNOSTIC_DISABLED"
                if control.policy.diagnostic is None
                else "DECLARED_DIAGNOSTIC_APPLIED_AFTER_GUARDS"
            ],
        ),
        StageResult(
            stage=RouterStage.W5_ROUTE,
            verdict=(
                GuardVerdict.PASS
                if route in {RouteDisposition.ADMIT, RouteDisposition.REOPEN}
                else (
                    GuardVerdict.UNRESOLVED
                    if route
                    in {
                        RouteDisposition.HOLD,
                        RouteDisposition.REQUEST_WITNESS,
                    }
                    else GuardVerdict.FAIL
                )
            ),
            reason_codes=[route.value],
        ),
        StageResult(
            stage=RouterStage.W6_RETURN,
            verdict=GuardVerdict.PASS,
            reason_codes=["ONE_NONEXECUTING_DECISION_RETURNED"],
        ),
    ]
    values: dict[str, Any] = {
        "schema_version": "0.1",
        "packet_id": proposal.packet_id,
        "proposal_hash": proposal_hash,
        "control_hash": control_hash,
        "policy_hash": policy_hash,
        "route": route,
        "selected_candidate_id": (None if selected is None else selected.candidate_id),
        "stages": stages,
        "candidates": evaluations,
        "reason_codes": reasons,
        "required_next_receipts": required,
        "mode": control.policy.mode,
        "nonexecution_marker": True,
        "authority": "NONE",
        "effect": "NONE",
        "limitations": LIMITATIONS,
    }
    return _finalize_decision(values)


def evaluate_route_raw(raw: bytes) -> RouteDecision:
    """Fail closed to a typed deterministic REJECT for malformed input."""

    raw_hash = raw_sha256(raw)
    try:
        value = load_bytes_strict(raw)
        request = RoutingRequest.model_validate(value)
        canonical_bytes(request)  # also rejects ambiguous nested numeric content
        return evaluate_route(request)
    except (CanonicalJSONError, ValidationError, ValueError, TypeError) as exc:
        values: dict[str, Any] = {
            "schema_version": "0.1",
            "packet_id": None,
            "proposal_hash": raw_hash,
            "control_hash": None,
            "policy_hash": None,
            "route": RouteDisposition.REJECT,
            "selected_candidate_id": None,
            "stages": [
                StageResult(
                    stage=RouterStage.W0_FREEZE,
                    verdict=GuardVerdict.FAIL,
                    reason_codes=["MALFORMED_OR_AMBIGUOUS_REQUEST"],
                ),
                StageResult(
                    stage=RouterStage.W6_RETURN,
                    verdict=GuardVerdict.PASS,
                    reason_codes=["ONE_NONEXECUTING_DECISION_RETURNED"],
                ),
            ],
            "candidates": [],
            "reason_codes": [
                "MALFORMED_OR_AMBIGUOUS_REQUEST",
                type(exc).__name__.upper(),
            ],
            "required_next_receipts": [],
            "mode": "SHADOW_ONLY",
            "nonexecution_marker": True,
            "authority": "NONE",
            "effect": "NONE",
            "limitations": LIMITATIONS,
        }
        return _finalize_decision(values)


__all__ = ["evaluate_route", "evaluate_route_raw"]
