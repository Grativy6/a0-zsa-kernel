from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus
from a0_zsa_kernel.models import TransitionPacket

from conftest import packet_dict


def test_unresolved_expiry_is_disabled_in_baseline():
    receipt = evaluate_packet(TransitionPacket.model_validate(packet_dict("UNRESOLVED", "EXPIRED")))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.UNRESOLVED


def test_profile_can_expire_named_presentation_window():
    data = packet_dict("UNRESOLVED", "EXPIRED")
    data["transition_profile"] = {"profile_id": "DEMO_WINDOWED", "allow_unresolved_expiry": True}
    data["expiry"] = {
        "subject": "PRESENTATION_WINDOW",
        "window_id": "window-001",
        "explanation": "The intake presentation window ended; unresolved possibility is not erased.",
    }
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.ALLOWED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.EXPIRED


def test_corrected_procedural_failure_does_not_persist_as_modifier():
    data = packet_dict("REJECTED", "CANDIDATE")
    old_id = data["candidate"]["candidate_id"]
    data["operation"] = "REOPEN"
    data["candidate"]["candidate_id"] = "cand-002"
    data["current_state"]["candidate_id"] = old_id
    failure = {
        "failure_id": "failure-001",
        "category": "PROCEDURAL",
        "code": "MISSING_FIELD",
        "description": "Required field was absent.",
        "correctable": True,
        "occurred_receipt_id": "sha256:prior",
    }
    data["trace"]["reopening"] = {
        "prior_candidate_id": old_id,
        "prior_candidate_content_hash": data["current_state"]["candidate_content_hash"],
        "prior_status": "REJECTED",
        "prior_receipt_id": "sha256:prior",
        "failures": [failure],
        "material_deltas": [
            {
                "category": "PROCEDURAL",
                "resolves_failure_ids": ["failure-001"],
                "field": "required_field",
                "before_hash": "sha256:missing",
                "after_hash": "sha256:present",
                "description": "Required field supplied.",
            }
        ],
        "declared_reopening_condition": "Required field is now present.",
    }
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.ALLOWED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.CANDIDATE
    assert receipt.retained_failures == []
    assert [item.failure_id for item in receipt.resolved_failures] == ["failure-001"]


def test_reopening_without_matching_material_delta_is_blocked():
    data = packet_dict("REJECTED", "CANDIDATE")
    old_id = data["candidate"]["candidate_id"]
    data["operation"] = "REOPEN"
    data["candidate"]["candidate_id"] = "cand-002"
    data["current_state"]["candidate_id"] = old_id
    data["trace"]["reopening"] = {
        "prior_candidate_id": old_id,
        "prior_candidate_content_hash": data["current_state"]["candidate_content_hash"],
        "prior_status": "REJECTED",
        "prior_receipt_id": "sha256:prior",
        "failures": [{
            "failure_id": "failure-002",
            "category": "AUTHORITY",
            "code": "NO_SCOPE",
            "description": "Authority scope absent.",
            "correctable": True,
            "occurred_receipt_id": "sha256:prior"
        }],
        "material_deltas": [{
            "category": "PROCEDURAL",
            "resolves_failure_ids": ["failure-002"],
            "field": "format",
            "before_hash": "sha256:a",
            "after_hash": "sha256:b",
            "description": "Only formatting changed."
        }],
        "declared_reopening_condition": "Authority must change."
    }
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert "MATERIAL_DELTA_MISSING" in receipt.reason_codes
