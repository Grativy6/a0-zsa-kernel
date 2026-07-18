from a0_zsa_kernel.engine import evaluate_raw
from a0_zsa_kernel.enums import AttemptOutcome


def test_malformed_packet_has_no_lifecycle_status():
    receipt = evaluate_raw(b'{"schema_version":"0.1",')
    assert receipt.attempt_outcome is AttemptOutcome.INVALID
    assert receipt.resulting_lifecycle_status is None


def test_duplicate_keys_are_invalid():
    receipt = evaluate_raw(b'{"packet_id":"one","packet_id":"two"}')
    assert receipt.attempt_outcome is AttemptOutcome.INVALID
