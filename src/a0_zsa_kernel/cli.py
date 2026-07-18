from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .canonical import canonical_bytes, loads_no_duplicates
from .engine import evaluate_raw
from .models import AttemptReceipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a0-zsa-kernel",
        description="Evaluate one local JSON transition packet and emit one JSON receipt.",
    )
    parser.add_argument("input", nargs="?", help="Input JSON file; stdin when omitted")
    parser.add_argument(
        "--replay-receipt",
        help="Audit deterministic replay against a prior receipt JSON file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    raw = Path(args.input).read_bytes() if args.input else sys.stdin.buffer.read()
    prior = None
    if args.replay_receipt:
        value = loads_no_duplicates(Path(args.replay_receipt).read_text(encoding="utf-8"))
        prior = AttemptReceipt.model_validate(value)
    receipt = evaluate_raw(raw, replay_receipt=prior)
    sys.stdout.buffer.write(canonical_bytes(receipt) + b"\n")
    return 0 if receipt.attempt_outcome.value in {"ALLOWED", "REPLAYED"} else 2
