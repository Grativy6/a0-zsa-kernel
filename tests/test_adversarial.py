import json

import pytest
from pydantic import ValidationError

from a0_zsa_kernel.engine import evaluate_packet
from a0_zsa_kernel.enums import AttemptOutcome, LifecycleStatus
from a0_zsa_kernel.models import TransitionPacket

from conftest import packet_dict


def test_binary_float_is_rejected_for_rule_values():
    data = packet_dict()
    data["weighting"]["factors"]["risk"] = 0.2
    with pytest.raises(ValidationError):
        TransitionPacket.model_validate(data)


def test_candidate_tampering_is_invalid_not_rejected():
    data = packet_dict()
    data["candidate"]["content"]["payload"] = "tampered"
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.INVALID
    assert receipt.resulting_lifecycle_status is LifecycleStatus.CANDIDATE


def test_json_round_trip_preserves_fixed_decimal_strings():
    data = packet_dict()
    encoded = json.dumps(data)
    packet = TransitionPacket.model_validate_json(encoded)
    assert str(packet.weighting.factors["risk"]) == "0.200000"


def test_tampered_rule_hash_is_invalid_without_lifecycle_mutation():
    data = packet_dict("MEASURED", "COMMITTED")
    data["admissibility_rule"]["governance"]["rule_hash"] = "sha256:tampered"
    receipt = evaluate_packet(TransitionPacket.model_validate(data))
    assert receipt.attempt_outcome is AttemptOutcome.INVALID
    assert receipt.resulting_lifecycle_status is LifecycleStatus.MEASURED
