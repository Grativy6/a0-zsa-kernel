from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus

from conftest import make_packet


def test_committed_cannot_flow_backward():
    receipt = evaluate_packet(make_packet("COMMITTED", "MEASURED"))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.COMMITTED
    assert receipt.source_record_unchanged


def test_expired_is_terminal():
    receipt = evaluate_packet(make_packet("EXPIRED", "CANDIDATE"))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.EXPIRED
