# A0 Boundary Kernel experimental prototypes

This repository now preserves two deliberately separate implementation
surfaces:

- `a0_zsa_kernel` is the frozen v0.1 lifecycle-transition prototype already
  present at commit `eb3505968a1b8a370862ce48f9f486b22a50cb17`.
- `a0bk_kernel` is a v0.2 successor namespace implementing selected A0BK
  v0.10.0 **candidate** mechanisms: native account openings, typed immutable
  receipts, exact legacy references, persistent residual identity, a serial
  SQLite evidence ledger, and deterministic W0-W6 Strongwiz shadow routing.

The second surface does not rewrite or retroactively upgrade the first. Its
bounded status and frozen source identities are recorded in
`docs/PROVENANCE.md`.

## Strongwiz shadow router

Strongwiz supplies proposals. A separately supplied strict control snapshot
supplies the declared active account, observation binding, policy, grant,
budget, evidence aperture, and serial-token state. The router evaluates eight
hard guards before any optional diagnostic and returns exactly one typed
route: `ADMIT`, `HOLD`, `REQUEST_WITNESS`, `REJECT`, or `REOPEN`.

Every result carries:

- `nonexecution_marker: true`
- `authority: "NONE"`
- `effect: "NONE"`

An `ADMIT` is only an advisory selection inside this shadow profile. It is not
permission and does not invoke an executor, game, connector, network service,
credential, or external model. See `docs/STRONGWIZ_ROUTING_PROFILE.md` for the
exact route semantics and claim ceiling.

### Native operations

The successor namespace exports:

```python
from a0bk_kernel import (
    append_receipt,
    evaluate_route,
    open_child,
    open_root,
    open_successor,
    open_version,
    register_residual,
    transition_residual,
    wrap_legacy_receipt,
)
```

`ROOT`, `CHILD`, and `SUCCESSOR` each require their own supplied cut and return
an atomic `AccountHeader` + `CutReceipt` bundle. `VERSION` preserves the same
account and origin only when exact one-step continuity and typed delta/witness
references are supplied. When earlier appends exist, the caller also supplies
the next global receipt admission order. Otherwise the constructor or ledger
refuses the operation; neither silently manufactures a successor cut.

The local `SQLiteLedger` commits openings and version transitions in one
`BEGIN IMMEDIATE` transaction, refuses non-identical rewrites, preserves exact
canonical bytes, and supports one-use serial tokens with idempotent exact
replay. This is a serial local profile, not a distributed or general A12
claim.

### Run the router

Install the project and test tools in an isolated environment, then pass
either one strict `RoutingRequest` or physically separate proposal and
control files:

```powershell
python -m pip install -e ".[test]"
python -m a0bk_kernel request.json
python -m a0bk_kernel --proposal proposal.json --control control.json
```

The command writes one canonical JSON decision. Exit code is `0` for `ADMIT`
or `REOPEN`, and `2` for a held, witness-requesting, rejected, or malformed
request. Malformed input still receives one deterministic, fail-closed,
nonexecuting `REJECT` decision.

## Legacy v0.1 prototype

This isolated Python CLI models declared transition attempts from unresolved or candidate material toward retained, software-readable state near the A1-to-A2 transition. It does not run at A0, simulate unresolved reality, prove PAL or ZSA, redefine ZSA, or create external authority.

ZSA-related language is used only in the bounded and attributed sense described by *A0 Boundary Kernel v0.8.2*: imported, ZSA-style first-order boundary bookkeeping attributed there to Lawrence Ip. This prototype does not reproduce or silently merge ZSA into PAL.

## Two separate axes

- Candidate lifecycle: `UNRESOLVED`, `CANDIDATE`, `WEIGHTED`, `MEASURED`, `COMMITTED`, `REJECTED`, `EXPIRED`.
- Attempt outcome: `ALLOWED`, `BLOCKED`, `INVALID`, `REPLAYED`.

Blocked, malformed, stale, or unauthorized attempts leave the candidate's lifecycle unchanged. `REJECTED` is reached only through an allowed lifecycle transition with an explicit rejection basis; it is not an error bucket for attempts.

## Determinism and canonical JSON

Deterministic replay comes from canonical serialization plus deterministic, local rules. SHA-256 hashes provide identity and tamper evidence; hashes do not make nondeterministic logic deterministic.

Canonical serialization uses UTF-8, lexicographically sorted object keys, no insignificant whitespace, array order preservation, minimal JSON string escaping with non-ASCII preserved, explicit nulls, uppercase enum values, UTC whole-second timestamps ending in `Z`, and fixed decimals encoded as JSON strings without exponent notation or negative zero and with at most six fractional places. Duplicate object keys are rejected. Rule evaluation never uses binary floating-point.

## Rule governance and authority

Every commitment rule declares an author, adopter, scope, effective interval, hash, and adoption-authority reference. The packet separately supplies the actor's authority context. A permissive rule cannot manufacture authority: rule adoption, current actor authority, action, target, scope, and effective intervals must all pass independently.

## Failure memory and reopening

Failure memory is typed as evidentiary, procedural, authority, integrity, or substantive. Reopening creates a new linked candidate and requires a declared material delta for every inherited failure category. A correctable procedural failure is removed from retained failure modifiers after a matching procedural delta; the historical receipt remains preserved. The source candidate is never rewritten.

`UNRESOLVED -> EXPIRED` is disabled in the baseline profile. A profile may enable it only when an explicit expiry declaration names the presentation, observation, or rule-eligibility window that expired. Unresolved possibility itself is not claimed to expire.

### Run

From this directory:

```powershell
$env:PYTHONPATH = "src"
python -m a0_zsa_kernel examples\valid_candidate_weighting.json
```

The CLI reads one JSON packet from a file or stdin and writes one canonical JSON receipt to stdout. It performs no network or external action. Exit code is `0` for `ALLOWED` or verified `REPLAYED`, and `2` for `BLOCKED` or `INVALID`.

Replay audit:

```powershell
python -m a0_zsa_kernel packet.json > receipt.json
python -m a0_zsa_kernel packet.json --replay-receipt receipt.json
```

## Verification

```powershell
python -m pytest
python -m ruff check .
python -m mypy
```

The legacy 22-test suite remains unchanged. Successor tests exercise strict
canonicalization, all native opening operations, closure separation, residual
lineage, guard precedence, diagnostics, malformed replay, atomic ledger
behavior, and serial-token refusal.

## Visibility and license

Public visibility makes the repository inspectable. No operative root
`LICENSE` is currently present, so visibility alone does not grant general
copy, modification, redistribution, or deployment rights. Attribution and
source hashes in `docs/PROVENANCE.md` describe where this implementation came
from; they are not a license or authority grant.
