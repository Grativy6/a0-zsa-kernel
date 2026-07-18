from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .canonical import loads_no_duplicates, raw_sha256, sha256_id
from .enums import AttemptOutcome, CheckResult, FailureCategory, LifecycleStatus, Operation
from .models import (
    AttemptReceipt,
    CheckRecord,
    EvidenceManifestEntry,
    ReplayAudit,
    TransitionPacket,
)
from .receipts import finalize_receipt
from .rules import commitment_errors, rule_body_hash
from .transitions import route_allowed


def _check(check_id: str, passed: bool, **details: Any) -> CheckRecord:
    return CheckRecord(
        check_id=check_id,
        result=CheckResult.PASS if passed else CheckResult.FAIL,
        details=details,
    )


def _base(packet: TransitionPacket, packet_hash: str) -> dict[str, Any]:
    evidence = [
        EvidenceManifestEntry(observation_id=item.observation_id, observation_hash=sha256_id(item))
        for item in packet.observations
    ]
    return {
        "schema_version": "0.1",
        "packet_id": packet.packet_id,
        "packet_hash": packet_hash,
        "attempted_transition": packet.requested_transition,
        "prior_lifecycle_status": packet.current_state.status,
        "resulting_lifecycle_status": packet.current_state.status,
        "lifecycle_changed": False,
        "source_record_unchanged": True,
        "control_modes": [packet.authority.control_mode] if packet.authority else [],
        "checks": [],
        "reason_codes": [],
        "candidate_snapshot_hash": sha256_id(packet.candidate),
        "evidence_manifest": evidence,
        "authority_snapshot_hash": sha256_id(packet.authority) if packet.authority else None,
        "admissibility_rule_hash": rule_body_hash(packet.admissibility_rule) if packet.admissibility_rule else None,
        "unresolved_burdens": packet.measurement.unresolved_burdens if packet.measurement else [],
        "reopening_conditions": [],
        "retained_failures": packet.trace.failures,
        "resolved_failures": [],
    }


def evaluate_packet(
    packet: TransitionPacket,
    replay_receipt: AttemptReceipt | None = None,
) -> AttemptReceipt:
    packet_hash = sha256_id(packet)
    data = _base(packet, packet_hash)
    checks: list[CheckRecord] = data["checks"]
    reasons: list[str] = data["reason_codes"]

    declared_content_hash = sha256_id(packet.candidate.content)
    content_ok = declared_content_hash == packet.candidate.content_hash
    checks.append(_check("candidate_content_hash", content_ok))
    if not content_ok:
        reasons.append("CANDIDATE_CONTENT_HASH_MISMATCH")

    state_matches = packet.current_state.status == packet.requested_transition.from_status
    if packet.operation is Operation.TRANSITION:
        state_matches = (
            state_matches
            and packet.current_state.candidate_id == packet.candidate.candidate_id
            and packet.current_state.candidate_content_hash == packet.candidate.content_hash
        )
    elif packet.trace.reopening:
        state_matches = (
            state_matches
            and packet.current_state.candidate_id == packet.trace.reopening.prior_candidate_id
            and packet.current_state.candidate_content_hash
            == packet.trace.reopening.prior_candidate_content_hash
        )
    checks.append(_check("current_state_binding", state_matches))
    if not state_matches:
        reasons.append("CURRENT_STATE_MISMATCH")

    if not content_ok or not state_matches:
        data["attempt_outcome"] = AttemptOutcome.INVALID
        base_receipt = finalize_receipt(data)
        return _as_replay(base_receipt, replay_receipt) if replay_receipt else base_receipt

    if packet.operation is Operation.REOPEN:
        base_receipt = _evaluate_reopening(packet, data)
        return _as_replay(base_receipt, replay_receipt) if replay_receipt else base_receipt

    source = packet.requested_transition.from_status
    target = packet.requested_transition.to_status
    allowed = route_allowed(
        source,
        target,
        allow_unresolved_expiry=packet.transition_profile.allow_unresolved_expiry,
    )
    checks.append(_check("lifecycle_route", allowed))
    if not allowed:
        reasons.append("TRANSITION_NOT_ALLOWED")

    if source is LifecycleStatus.UNRESOLVED and target is LifecycleStatus.EXPIRED:
        expiry_ok = packet.expiry is not None and packet.expiry.subject.value != "CANDIDATE_ELIGIBILITY"
        checks.append(_check("unresolved_expiry_subject", expiry_ok))
        if not expiry_ok:
            reasons.append("UNRESOLVED_EXPIRY_SUBJECT_REQUIRED")

    stale = packet.candidate.expires_at is not None and packet.evaluation_time >= packet.candidate.expires_at
    if target is LifecycleStatus.EXPIRED:
        expiry_ok = stale or packet.expiry is not None
        checks.append(_check("expiry_basis", expiry_ok))
        if not expiry_ok:
            reasons.append("EXPIRY_BASIS_MISSING")
    elif stale:
        checks.append(_check("candidate_current", False))
        reasons.append("CANDIDATE_STALE")

    if target is LifecycleStatus.WEIGHTED and packet.weighting is None:
        reasons.append("WEIGHTING_MISSING")
    if target is LifecycleStatus.MEASURED and packet.measurement is None:
        reasons.append("MEASUREMENT_MISSING")
    if target in {LifecycleStatus.COMMITTED, LifecycleStatus.REJECTED}:
        reasons.extend(commitment_errors(packet))
        if target is LifecycleStatus.REJECTED:
            explicit_failure = bool(packet.weighting and packet.weighting.hard_vetoes) or any(
                f.category in {FailureCategory.INTEGRITY, FailureCategory.SUBSTANTIVE}
                for f in packet.trace.failures
            )
            if not explicit_failure:
                reasons.append("REJECTION_BASIS_MISSING")

    if reasons:
        data["attempt_outcome"] = (
            AttemptOutcome.INVALID if "RULE_HASH_MISMATCH" in reasons else AttemptOutcome.BLOCKED
        )
    else:
        data["attempt_outcome"] = AttemptOutcome.ALLOWED
        data["resulting_lifecycle_status"] = target
        data["lifecycle_changed"] = target != source
    base_receipt = finalize_receipt(data)
    return _as_replay(base_receipt, replay_receipt) if replay_receipt else base_receipt


def _evaluate_reopening(packet: TransitionPacket, data: dict[str, Any]) -> AttemptReceipt:
    reopening = packet.trace.reopening
    reasons: list[str] = data["reason_codes"]
    checks: list[CheckRecord] = data["checks"]
    valid = reopening is not None
    if valid and reopening:
        valid = (
            packet.requested_transition.to_status is LifecycleStatus.CANDIDATE
            and reopening.prior_candidate_id == packet.current_state.candidate_id
            and reopening.prior_status == packet.current_state.status
            and packet.candidate.candidate_id != reopening.prior_candidate_id
            and bool(reopening.material_deltas)
            and (
                packet.current_state.last_receipt_id is None
                or packet.current_state.last_receipt_id == reopening.prior_receipt_id
            )
        )
    checks.append(_check("reopening_structure", valid))
    if not valid or reopening is None:
        reasons.append("INVALID_REOPENING_STRUCTURE")
        data["attempt_outcome"] = AttemptOutcome.INVALID
        return finalize_receipt(data)

    resolution_pairs = {
        (failure_id, delta.category)
        for delta in reopening.material_deltas
        for failure_id in delta.resolves_failure_ids
    }
    unmet = sorted(
        failure.failure_id
        for failure in reopening.failures
        if (failure.failure_id, failure.category) not in resolution_pairs
    )
    checks.append(_check("material_delta", not unmet, unmet_failure_ids=unmet))
    if unmet:
        reasons.append("MATERIAL_DELTA_MISSING")

    resolved_procedural = [
        failure
        for failure in reopening.failures
        if failure.category is FailureCategory.PROCEDURAL
        and failure.correctable
        and (failure.failure_id, failure.category) in resolution_pairs
    ]
    retained = [
        failure
        for failure in reopening.failures
        if failure not in resolved_procedural
    ]
    data["retained_failures"] = retained
    data["resolved_failures"] = resolved_procedural
    data["reopening_conditions"] = [reopening.declared_reopening_condition]
    if reasons:
        data["attempt_outcome"] = AttemptOutcome.BLOCKED
    else:
        data["attempt_outcome"] = AttemptOutcome.ALLOWED
        data["resulting_lifecycle_status"] = LifecycleStatus.CANDIDATE
        data["lifecycle_changed"] = True
        data["source_record_unchanged"] = True
    return finalize_receipt(data)


def _as_replay(base: AttemptReceipt, prior: AttemptReceipt) -> AttemptReceipt:
    matches = base.receipt_id == prior.receipt_id and base.decision_id == prior.decision_id
    data = base.model_dump(mode="python")
    data["attempt_outcome"] = AttemptOutcome.REPLAYED if matches else AttemptOutcome.INVALID
    data["lifecycle_changed"] = False
    if not matches:
        data["reason_codes"] = [*data["reason_codes"], "REPLAY_MISMATCH"]
    data["replay_audit"] = ReplayAudit(
        original_receipt_id=prior.receipt_id,
        original_decision_id=prior.decision_id,
        receipt_matches=base.receipt_id == prior.receipt_id,
        decision_matches=base.decision_id == prior.decision_id,
    )
    data.pop("receipt_id", None)
    return finalize_receipt(data)


def evaluate_raw(raw: bytes, replay_receipt: AttemptReceipt | None = None) -> AttemptReceipt:
    packet_hash = raw_sha256(raw)
    try:
        decoded = raw.decode("utf-8")
        value = loads_no_duplicates(decoded)
        packet = TransitionPacket.model_validate(value)
    except (UnicodeDecodeError, ValueError, ValidationError):
        return finalize_receipt(
            {
                "schema_version": "0.1",
                "packet_id": None,
                "packet_hash": packet_hash,
                "attempt_outcome": AttemptOutcome.INVALID,
                "attempted_transition": None,
                "prior_lifecycle_status": None,
                "resulting_lifecycle_status": None,
                "lifecycle_changed": False,
                "source_record_unchanged": True,
                "checks": [_check("packet_schema", False)],
                "reason_codes": ["MALFORMED_OR_INVALID_PACKET"],
            }
        )
    return evaluate_packet(packet, replay_receipt=replay_receipt)
