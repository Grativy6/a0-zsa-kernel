# A0 Boundary Kernel experimental prototype

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

## Run

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

## Tests

```powershell
python -m pytest
```
