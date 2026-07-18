from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus
from a0_zsa_kernel.models import TransitionPacket

from conftest import packet_dict


def test_attempt_outcome_and_lifecycle_are_independent():
    data = packet_dict("MEASURED", "COMMITTED")
    data["authority"] = None
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.prior_lifecycle_status is LifecycleStatus.MEASURED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.MEASURED


def test_receipt_preserves_evidence_hashes():
    receipt = evaluate_packet(TransitionPacket.model_validate(packet_dict()))
    assert receipt.evidence_manifest[0].observation_hash.startswith("sha256:")
    assert receipt.candidate_snapshot_hash.startswith("sha256:")
