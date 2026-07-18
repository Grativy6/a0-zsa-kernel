from __future__ import annotations

from decimal import Decimal

from .canonical import sha256_id
from .models import AdmissibilityRule, TransitionPacket


def rule_body_hash(rule: AdmissibilityRule) -> str:
    body = rule.model_dump(mode="python")
    body["governance"] = dict(body["governance"])
    body["governance"].pop("rule_hash", None)
    return sha256_id(body)


def rule_governance_errors(packet: TransitionPacket) -> list[str]:
    rule = packet.admissibility_rule
    if rule is None:
        return ["RULE_MISSING"]
    errors: list[str] = []
    governance = rule.governance
    if governance.rule_hash != rule_body_hash(rule):
        errors.append("RULE_HASH_MISMATCH")
    if not governance.effective_from <= packet.evaluation_time < governance.effective_until:
        errors.append("RULE_NOT_EFFECTIVE")
    if governance.scope != packet.authority.scope if packet.authority else True:
        errors.append("RULE_SCOPE_MISMATCH")
    if packet.authority is None:
        errors.append("AUTHORITY_MISSING")
    elif governance.authority_reference not in packet.authority.rule_adoption_authority_refs:
        errors.append("RULE_ADOPTION_AUTHORITY_MISSING")
    return errors


def commitment_errors(packet: TransitionPacket) -> list[str]:
    rule = packet.admissibility_rule
    authority = packet.authority
    errors = rule_governance_errors(packet)
    if rule is None or authority is None:
        return errors
    requested = packet.requested_transition
    if rule.permitted_transition.from_status != requested.from_status or rule.permitted_transition.to_status != requested.to_status:
        errors.append("RULE_TRANSITION_MISMATCH")
    if not authority.valid_from <= packet.evaluation_time < authority.valid_until:
        errors.append("AUTHORITY_NOT_CURRENT")
    if rule.required_authority_action not in authority.allowed_actions:
        errors.append("ACTION_NOT_AUTHORIZED")
    if packet.candidate.candidate_id not in authority.allowed_targets:
        errors.append("TARGET_NOT_AUTHORIZED")
    observed_kinds = {item.kind for item in packet.observations}
    if not set(rule.required_observation_kinds).issubset(observed_kinds):
        errors.append("REQUIRED_EVIDENCE_MISSING")
    if packet.weighting is None:
        errors.append("WEIGHTING_MISSING")
    else:
        for key, floor in rule.minimum_weights.items():
            if packet.weighting.factors.get(key, Decimal("-1")) < floor:
                errors.append(f"MINIMUM_WEIGHT_FAILED:{key}")
        for key, ceiling in rule.maximum_weights.items():
            if packet.weighting.factors.get(key, Decimal("2")) > ceiling:
                errors.append(f"MAXIMUM_WEIGHT_FAILED:{key}")
        if packet.weighting.hard_vetoes:
            errors.append("HARD_VETO_ACTIVE")
    if packet.measurement is None:
        errors.append("MEASUREMENT_MISSING")
    else:
        missing = set(packet.measurement.unresolved_burdens) - set(rule.allowed_unresolved_burdens)
        if missing:
            errors.append("UNRESOLVED_BURDEN_NOT_ALLOWED")
        observation_ids = {item.observation_id for item in packet.observations}
        if not set(packet.measurement.observation_refs).issubset(observation_ids):
            errors.append("MEASUREMENT_REFERENCE_MISSING")
    return errors
