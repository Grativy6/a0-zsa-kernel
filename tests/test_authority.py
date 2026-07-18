from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus
from a0_zsa_kernel.models import TransitionPacket

from conftest import packet_dict


def test_unauthorized_commit_attempt_does_not_reject_candidate():
    data = packet_dict("MEASURED", "COMMITTED")
    data["authority"]["allowed_actions"] = []
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.MEASURED
    assert "ACTION_NOT_AUTHORIZED" in receipt.reason_codes


def test_permissive_rule_cannot_manufacture_adoption_authority():
    data = packet_dict("MEASURED", "COMMITTED")
    data["authority"]["rule_adoption_authority_refs"] = []
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert "RULE_ADOPTION_AUTHORITY_MISSING" in receipt.reason_codes


def test_governed_authorized_commit_is_allowed():
    receipt = evaluate_packet(TransitionPacket.model_validate(packet_dict("MEASURED", "COMMITTED")))
    assert receipt.attempt_outcome is AttemptOutcome.ALLOWED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.COMMITTED
