from __future__ import annotations

from copy import deepcopy

from a0_zsa_kernel.canonical import sha256_id
from a0_zsa_kernel.models import AdmissibilityRule, TransitionPacket
from a0_zsa_kernel.rules import rule_body_hash


def packet_dict(source="CANDIDATE", target="WEIGHTED"):
    content = {"action": "retain-example", "payload": "deterministic"}
    content_hash = sha256_id(content)
    data = {
        "schema_version": "0.1",
        "packet_id": f"pkt-{source.lower()}-{target.lower()}",
        "operation": "TRANSITION",
        "evaluation_time": "2026-07-17T12:00:00Z",
        "candidate": {
            "candidate_id": "cand-001",
            "kind": "example_action",
            "content": content,
            "created_at": "2026-07-17T11:00:00Z",
            "expires_at": "2026-07-18T11:00:00Z",
            "content_hash": content_hash,
        },
        "current_state": {
            "candidate_id": "cand-001",
            "status": source,
            "candidate_content_hash": content_hash,
            "evidence_manifest_hash": None,
            "last_receipt_id": None,
        },
        "requested_transition": {
            "from_status": source,
            "to_status": target,
            "reason": "deterministic test",
        },
        "observations": [
            {
                "observation_id": "obs-001",
                "kind": "declared_fact",
                "value": {"present": True},
                "source": {"source_id": "fixture", "source_type": "test"},
                "observed_at": "2026-07-17T11:05:00Z",
                "evidence_strength": "0.800000",
            }
        ],
        "weighting": {
            "rule_id": "weights-v1",
            "factors": {
                "authority": "0.700000",
                "risk": "0.200000",
                "traceability": "1.000000",
            },
            "result": "0.650000",
            "hard_vetoes": [],
        },
        "measurement": {
            "measurement_id": "measure-001",
            "purpose": "local test classification",
            "method": "fixture",
            "observation_refs": ["obs-001"],
            "result": {"classification": "bounded"},
            "uncertainty": {"note": "fixture only"},
            "unresolved_burdens": [],
        },
        "authority": {
            "actor_id": "operator-001",
            "actor_type": "HUMAN",
            "lineage": ["operator-001"],
            "allowed_actions": ["commit_example", "reject_example"],
            "allowed_targets": ["cand-001"],
            "valid_from": "2026-07-17T00:00:00Z",
            "valid_until": "2026-07-18T00:00:00Z",
            "scope": "local-prototype-only",
            "control_mode": "trace",
            "credential_ref": "actor-authority-v1",
            "rule_adoption_authority_refs": ["adoption-authority-v1"],
        },
        "admissibility_rule": None,
        "transition_profile": {"profile_id": "BASELINE", "allow_unresolved_expiry": False},
        "expiry": None,
        "trace": {
            "previous_receipt_id": None,
            "parent_candidate_id": None,
            "inherited_receipt_ids": [],
            "failures": [],
            "reopening": None,
        },
    }
    if target in {"COMMITTED", "REJECTED"}:
        data["admissibility_rule"] = governed_rule(source, target)
    return data


def governed_rule(source="MEASURED", target="COMMITTED"):
    rule_data = {
        "rule_id": f"{source.lower()}-{target.lower()}-v1",
        "rule_version": "1",
        "governance": {
            "author": "prototype-author",
            "adopter": "prototype-adopter",
            "scope": "local-prototype-only",
            "effective_from": "2026-07-17T00:00:00Z",
            "effective_until": "2026-07-18T00:00:00Z",
            "rule_hash": "sha256:placeholder",
            "authority_reference": "adoption-authority-v1",
        },
        "permitted_transition": {"from_status": source, "to_status": target},
        "required_observation_kinds": ["declared_fact"],
        "minimum_weights": {"authority": "0.600000", "traceability": "1.000000"},
        "maximum_weights": {"risk": "0.400000"},
        "required_authority_action": "commit_example" if target == "COMMITTED" else "reject_example",
        "allowed_unresolved_burdens": [],
        "veto_conditions": [],
    }
    provisional = AdmissibilityRule.model_validate(rule_data)
    rule_data["governance"]["rule_hash"] = rule_body_hash(provisional)
    return rule_data


def make_packet(source="CANDIDATE", target="WEIGHTED") -> TransitionPacket:
    return TransitionPacket.model_validate(packet_dict(source, target))


def clone(value):
    return deepcopy(value)
