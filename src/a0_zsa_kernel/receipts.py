from __future__ import annotations

from typing import Any

from .canonical import sha256_id
from .models import AttemptReceipt

NON_CLAIMS = [
    "This receipt records a bounded software protocol result near the A1-to-A2 transition.",
    "It does not run at A0, simulate unresolved reality, or prove PAL or ZSA.",
    "It does not create external execution, ethical, legal, or institutional authority.",
    "Machine success does not prove that supplied evidence or authority was complete or honest.",
]


def finalize_receipt(data: dict[str, Any]) -> AttemptReceipt:
    decision_material = {
        "packet_hash": data["packet_hash"],
        "attempted_transition": data.get("attempted_transition"),
        "prior_lifecycle_status": data.get("prior_lifecycle_status"),
        "resulting_lifecycle_status": data.get("resulting_lifecycle_status"),
        "reason_codes": data.get("reason_codes", []),
        "checks": data.get("checks", []),
    }
    data.setdefault("decision_id", sha256_id(decision_material))
    data.setdefault("non_claims", NON_CLAIMS)
    receipt_material = dict(data)
    receipt_material.pop("receipt_id", None)
    data["receipt_id"] = sha256_id(receipt_material)
    return AttemptReceipt.model_validate(data)
