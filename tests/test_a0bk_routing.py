from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from a0bk_kernel.canonical import CanonicalJSONError, canonical_bytes, sha256_id
from a0bk_kernel.models import (
    BudgetSnapshot,
    CandidateProposal,
    ConsequenceClass,
    ControlSnapshot,
    DecisionEffect,
    DiagnosticDimension,
    DiagnosticProfile,
    GrantSnapshot,
    GuardDefinition,
    GuardId,
    GuardVerdict,
    ProposalPacket,
    RouteDecision,
    RouteDisposition,
    RouterPolicy,
    RouterStage,
    RoutingRequest,
)
from a0bk_kernel.routing import evaluate_route, evaluate_route_raw

NOW = datetime(2026, 1, 1, 12, tzinfo=UTC)
ACCOUNT = sha256_id({"fixture": "account"})
OBSERVATION = sha256_id({"fixture": "observation"})
EVIDENCE = sha256_id({"fixture": "evidence"})
TRACE = sha256_id({"fixture": "trace"})
RESIDUAL = sha256_id({"fixture": "residual"})
TOKEN = sha256_id({"fixture": "token"})
DELTA = sha256_id({"fixture": "material-delta"})
TARGET = "grid:1,1"


def _ref(label: str) -> str:
    return sha256_id({"label": label})


def _candidate(**overrides: object) -> CandidateProposal:
    values: dict[str, object] = {
        "candidate_id": "candidate-move",
        "proposed_rank": 0,
        "action_id": "MOVE",
        "target_ref": TARGET,
        "predicted_consequence": {"position": "next"},
        "meaningful_distinction": "could change movement plan",
        "decision_effects": [DecisionEffect.MOVEMENT, DecisionEffect.PLAN],
        "evidence_refs": [EVIDENCE],
        "conflicting_evidence_refs": [],
        "residual_refs": [RESIDUAL],
        "material_delta_refs": [],
        "reopens_account_ref": None,
        "uncertainty": "0.2",
        "metrics": {"information_gain": "0.5"},
        "action_cost": 1,
        "life_cost": 0,
        "reversible": True,
        "consequence_class": ConsequenceClass.REVERSIBLE,
        "summary_reason": "small discriminating move",
    }
    values.update(overrides)
    return CandidateProposal.model_validate(values)


def _policy(*, diagnostic: bool = False) -> RouterPolicy:
    profile = None
    if diagnostic:
        profile = DiagnosticProfile(
            profile_id="diagnostic-v1",
            profile_version="1",
            purpose="rank only candidates that passed every hard guard",
            decision_not_permitted="cannot override a guard",
            dimensions=[DiagnosticDimension(name="information_gain", weight="1.0")],
            sensitivity_ref=_ref("sensitivity"),
            calibration_ref=_ref("calibration"),
            limitations=["fixture calibration only"],
            expires_at=NOW + timedelta(hours=1),
        )
    return RouterPolicy(
        policy_id="strongwiz-shadow-test",
        policy_version="0.1",
        source_ref=_ref("policy-source"),
        scope="public-development-play",
        guards=[
            GuardDefinition(
                guard_id=guard_id,
                source_ref=_ref(f"guard:{guard_id.value}"),
                source_version="1",
                authority_ceiling="advisory only",
            )
            for guard_id in GuardId
        ],
        diagnostic=profile,
        allow_external_proposals=False,
        non_claims=["no execution authority"],
    )


def _request(
    *,
    candidates: list[CandidateProposal] | None = None,
    available_evidence: list[str] | None = None,
    budget: BudgetSnapshot | None = None,
    account_version: int = 1,
    control_account_version: int = 1,
    diagnostic: bool = False,
    grant_actions: list[str] | None = None,
    action_space: list[str] | None = None,
) -> RoutingRequest:
    proposal = ProposalPacket(
        packet_id="packet-1",
        root_goal="reach an observed terminal win",
        scoped_goal="test movement",
        active_account_ref=ACCOUNT,
        active_account_version=account_version,
        observation_ref=_ref("observation-object"),
        observation_hash=OBSERVATION,
        action_space=action_space or ["MOVE"],
        candidates=candidates or [_candidate()],
        prior_receipt_refs=[TRACE],
        candidate_generator_ref=_ref("candidate-generator"),
        generated_at=NOW,
    )
    grant = GrantSnapshot(
        grant_id=_ref("grant"),
        issuer_id="owner",
        actor_id="shadow-router",
        purpose="public development shadow audit",
        scope="public-development-play",
        allowed_action_ids=grant_actions or ["MOVE"],
        allowed_target_refs=[TARGET],
        valid_from=NOW - timedelta(minutes=1),
        valid_until=NOW + timedelta(minutes=1),
        nonce_ref=TOKEN,
        trust_root_ref=_ref("trust-root"),
    )
    control = ControlSnapshot(
        control_id=_ref("control"),
        evaluated_at=NOW,
        active_account_ref=ACCOUNT,
        active_account_version=control_account_version,
        current_observation_hash=OBSERVATION,
        available_evidence_refs=(
            [EVIDENCE] if available_evidence is None else available_evidence
        ),
        available_trace_refs=[TRACE],
        active_residual_refs=[RESIDUAL],
        budget=budget
        or BudgetSnapshot(
            remaining_actions=10,
            remaining_lives=3,
            remaining_wall_clock_ms=10_000,
        ),
        grant=grant,
        serial_token_ref=TOKEN,
        consumed_serial_token_refs=[],
        policy=_policy(diagnostic=diagnostic),
    )
    return RoutingRequest(proposal=proposal, control=control)


def test_route_admit_is_deterministic_nonexecuting_and_runs_w0_through_w6() -> None:
    request = _request()
    first = evaluate_route(request)
    second = evaluate_route(request)

    assert first == second
    assert first.decision_id == second.decision_id
    assert first.route is RouteDisposition.ADMIT
    assert first.selected_candidate_id == "candidate-move"
    assert first.authority == "NONE"
    assert first.effect == "NONE"
    assert first.nonexecution_marker is True
    assert [stage.stage for stage in first.stages] == list(RouterStage)
    assert first.stages[-1].verdict is GuardVerdict.PASS
    assert canonical_bytes(first) == canonical_bytes(second)

    raw_decision = evaluate_route_raw(canonical_bytes(request))
    assert raw_decision == first

    tampered = first.model_dump(mode="python")
    tampered["reason_codes"] = ["RETROACTIVE_REASON_REWRITE"]
    with pytest.raises(ValidationError, match="decision identity"):
        RouteDecision.model_validate(tampered)


def test_proposal_plane_cannot_supply_control_plane_fields() -> None:
    values = _request().proposal.model_dump(mode="python")
    values["grant"] = _request().control.grant.model_dump(mode="python")
    values["serial_token_ref"] = TOKEN
    values["policy"] = _request().control.policy.model_dump(mode="python")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProposalPacket.model_validate(values)


def test_untyped_consequence_decimal_cannot_collide_with_string() -> None:
    with pytest.raises(ValidationError, match="forbidden programmatic JSON type"):
        _candidate(predicted_consequence={"resource": Decimal("1")})
    string_candidate = _candidate(predicted_consequence={"resource": "1"})
    assert string_candidate.predicted_consequence == {"resource": "1"}
    bypass_attempt = string_candidate.model_copy(
        update={"predicted_consequence": {"resource": Decimal("1")}}
    )
    with pytest.raises(CanonicalJSONError, match="forbidden programmatic JSON type"):
        canonical_bytes(bypass_attempt)


def test_route_requests_witness_when_required_evidence_is_missing() -> None:
    decision = evaluate_route(_request(available_evidence=[]))
    assert decision.route is RouteDisposition.REQUEST_WITNESS
    assert decision.selected_candidate_id is None
    assert "EvidenceReceipt" in decision.required_next_receipts
    witness = next(
        result
        for result in decision.candidates[0].guard_results
        if result.guard_id is GuardId.WITNESS
    )
    assert witness.verdict is GuardVerdict.UNRESOLVED
    assert EVIDENCE in witness.evidence_refs


@pytest.mark.parametrize(
    "route_request",
    [
        _request(
            budget=BudgetSnapshot(
                remaining_actions=0,
                remaining_lives=3,
                remaining_wall_clock_ms=10_000,
            )
        ),
        _request(
            candidates=[
                _candidate(
                    reversible=False,
                    consequence_class=ConsequenceClass.IRREVERSIBLE,
                )
            ]
        ),
    ],
)
def test_route_holds_resource_or_consequence_boundaries(
    route_request: RoutingRequest,
) -> None:
    decision = evaluate_route(route_request)
    assert decision.route is RouteDisposition.HOLD
    assert decision.selected_candidate_id is None
    assert decision.required_next_receipts == ["UpdatedControlSnapshot"]


def test_route_rejects_hard_identity_failure() -> None:
    decision = evaluate_route(_request(control_account_version=2))
    assert decision.route is RouteDisposition.REJECT
    assert decision.selected_candidate_id is None
    assert "ACCOUNT_VERSION_MISMATCH" in decision.reason_codes


def test_route_reopens_only_with_material_delta_evidence() -> None:
    reopening = _candidate(
        material_delta_refs=[DELTA],
        reopens_account_ref=_ref("prior-account"),
    )
    decision = evaluate_route(
        _request(candidates=[reopening], available_evidence=[EVIDENCE, DELTA])
    )
    assert decision.route is RouteDisposition.REOPEN
    assert decision.selected_candidate_id == reopening.candidate_id
    assert decision.required_next_receipts == [
        "LifecycleTransitionReceipt",
        "MaterialDeltaReceipt",
    ]

    missing_delta = evaluate_route(
        _request(candidates=[reopening], available_evidence=[EVIDENCE])
    )
    assert missing_delta.route is RouteDisposition.REQUEST_WITNESS


def test_diagnostics_cannot_override_a_failed_hard_guard() -> None:
    forbidden = _candidate(
        candidate_id="forbidden-high-score",
        proposed_rank=0,
        action_id="BLOCKED",
        metrics={"information_gain": "1.0"},
    )
    eligible = _candidate(
        candidate_id="eligible-low-score",
        proposed_rank=1,
        metrics={"information_gain": "0.1"},
    )
    decision = evaluate_route(
        _request(
            candidates=[forbidden, eligible],
            diagnostic=True,
            grant_actions=["MOVE"],
            action_space=["MOVE", "BLOCKED"],
        )
    )
    assert decision.route is RouteDisposition.ADMIT
    assert decision.selected_candidate_id == eligible.candidate_id
    by_id = {item.candidate_id: item for item in decision.candidates}
    assert by_id[forbidden.candidate_id].eligible is False
    assert by_id[forbidden.candidate_id].diagnostic_score is None
    scope = next(
        result
        for result in by_id[forbidden.candidate_id].guard_results
        if result.guard_id is GuardId.SCOPE
    )
    assert scope.verdict is GuardVerdict.FAIL


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b'{"proposal":1,"proposal":2}',
        b'{"ambiguous":1.0}',
        b"\xff",
    ],
)
def test_malformed_or_ambiguous_raw_request_returns_one_deterministic_reject(
    raw: bytes,
) -> None:
    first = evaluate_route_raw(raw)
    second = evaluate_route_raw(raw)
    assert first == second
    assert first.route is RouteDisposition.REJECT
    assert first.packet_id is None
    assert first.selected_candidate_id is None
    assert first.authority == "NONE"
    assert first.effect == "NONE"
    assert [stage.stage for stage in first.stages] == [
        RouterStage.W0_FREEZE,
        RouterStage.W6_RETURN,
    ]
    assert "MALFORMED_OR_AMBIGUOUS_REQUEST" in first.reason_codes
