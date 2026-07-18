from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome

from conftest import make_packet


def test_same_packet_same_receipt_identity():
    packet = make_packet()
    assert evaluate_packet(packet).receipt_id == evaluate_packet(packet).receipt_id


def test_replay_audit_is_separate_attempt_outcome():
    packet = make_packet()
    original = evaluate_packet(packet)
    replay = evaluate_packet(packet, replay_receipt=original)
    assert replay.attempt_outcome is AttemptOutcome.REPLAYED
    assert replay.replay_audit.receipt_matches
    assert replay.replay_audit.decision_matches
    assert not replay.lifecycle_changed
