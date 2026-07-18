from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus

from conftest import make_packet


def test_candidate_can_become_weighted():
    receipt = evaluate_packet(make_packet())
    assert receipt.attempt_outcome is AttemptOutcome.ALLOWED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.WEIGHTED


def test_nonadjacent_jump_is_blocked_without_mutation():
    receipt = evaluate_packet(make_packet("CANDIDATE", "COMMITTED"))
    assert receipt.attempt_outcome is AttemptOutcome.BLOCKED
    assert receipt.resulting_lifecycle_status is LifecycleStatus.CANDIDATE
    assert not receipt.lifecycle_changed
