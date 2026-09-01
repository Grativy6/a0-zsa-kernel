"""Command line entry point for the nonexecuting successor router."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .canonical import (
    CanonicalJSONError,
    canonical_bytes,
    canonical_text,
    load_bytes_strict,
    raw_sha256,
)
from .models import RouteDisposition
from .routing import evaluate_route_raw


def _read(path: str | None) -> bytes:
    if path is None or path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a0bk-route",
        description="Return one deterministic, advisory, nonexecuting route decision.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        help="RoutingRequest JSON path, or '-' for stdin",
    )
    parser.add_argument("--proposal", help="separate ProposalPacket JSON path")
    parser.add_argument("--control", help="separate ControlSnapshot JSON path")
    parser.add_argument("--output", help="write the decision to a file")
    return parser


def _request_bytes(arguments: argparse.Namespace) -> bytes:
    separate = arguments.proposal is not None or arguments.control is not None
    if separate:
        if arguments.request is not None:
            raise ValueError("request path cannot be combined with separate inputs")
        if arguments.proposal is None or arguments.control is None:
            raise ValueError("--proposal and --control must be supplied together")
        proposal_raw = _read(arguments.proposal)
        control_raw = _read(arguments.control)
        try:
            proposal = load_bytes_strict(proposal_raw)
            control = load_bytes_strict(control_raw)
            return canonical_bytes(
                {"schema_version": "0.1", "proposal": proposal, "control": control}
            )
        except CanonicalJSONError:
            return canonical_bytes(
                {
                    "invalid_separate_input": True,
                    "proposal_raw_hash": raw_sha256(proposal_raw),
                    "control_raw_hash": raw_sha256(control_raw),
                }
            )
    return _read(arguments.request)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        raw = _request_bytes(arguments)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    decision = evaluate_route_raw(raw)
    rendered = canonical_text(decision) + "\n"
    if arguments.output:
        Path(arguments.output).write_text(rendered, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered)
    return (
        0 if decision.route in {RouteDisposition.ADMIT, RouteDisposition.REOPEN} else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
