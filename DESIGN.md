# Revised design record

This record incorporates the six approved corrections. Source meanings and non-claims are summarized in `reference/`; implementation details here are prototype choices, not amendments to PAL or ZSA.

## Status and attempt semantics

Lifecycle and attempt outcome are independent:

| Attempt outcome | Meaning | Lifecycle effect |
|---|---|---|
| `ALLOWED` | The packet passed the deterministic rules. | The declared allowed transition or new-candidate creation occurs. |
| `BLOCKED` | A well-formed attempt lacks a gate condition, is stale, unauthorized, or requests a blocked route. | Existing lifecycle remains unchanged. |
| `INVALID` | Packet, binding, candidate hash, or governed rule integrity is invalid. | Existing lifecycle remains unchanged; malformed input has no inferred lifecycle. |
| `REPLAYED` | Re-evaluation matches both the prior receipt and decision identities. | Audit-only; no additional lifecycle change. |

`REJECTED` is a candidate lifecycle state, not an attempt error. Rejection requires an allowed route, a governed rule, and an explicit substantive or integrity failure basis or declared hard veto.

## Transition semantics

The baseline routes are:

| From | Allowed destinations |
|---|---|
| `UNRESOLVED` | `CANDIDATE` |
| `CANDIDATE` | `WEIGHTED`, `REJECTED`, `EXPIRED` |
| `WEIGHTED` | `MEASURED`, `REJECTED`, `EXPIRED` |
| `MEASURED` | `COMMITTED`, `REJECTED`, `EXPIRED` |
| `COMMITTED` | `EXPIRED` |
| `REJECTED` | `EXPIRED` |
| `EXPIRED` | none |

`UNRESOLVED -> EXPIRED` is a profile extension. It must identify the presentation, observation, or rule-eligibility window that expired. It does not claim that unresolved possibility itself ceased to exist.

Reopening is not backward flow. A `REOPEN` operation binds the prior candidate ID, prior content hash, status, and receipt; supplies a new candidate ID; and declares material deltas resolving named failure IDs. The old record remains unchanged.

## Input schema

`TransitionPacket` contains:

- packet identity, operation, and caller-supplied UTC evaluation time;
- immutable candidate snapshot and content hash;
- bound current-state snapshot;
- requested lifecycle transition;
- separate observations, weighting, measurement, authority, and admissibility rule objects;
- transition profile and typed expiry declaration;
- trace context with typed failures and optional reopening packet.

Rule-relevant numeric values use fixed-decimal strings with zero to six fractional places. Binary JSON floats and exponent notation are invalid.

`AdmissibilityRule.governance` requires `author`, `adopter`, `scope`, `effective_from`, `effective_until`, `rule_hash`, and `authority_reference`. The actor context separately names allowed action, target, scope, interval, credential, and accepted rule-adoption authority references.

`FailureRecord.category` is one of `EVIDENTIARY`, `PROCEDURAL`, `AUTHORITY`, `INTEGRITY`, or `SUBSTANTIVE`. Each `MaterialDelta` names the exact failure IDs it resolves. Corrected, correctable procedural failures move to `resolved_failures`; they do not remain active modifiers. Their history remains in the packet/receipt chain.

## Receipt schema

Every attempt emits an `AttemptReceipt` with:

- packet hash, decision ID, and receipt ID;
- separate attempt outcome and prior/resulting lifecycle statuses;
- lifecycle-change and source-record-unchanged flags;
- checks and stable reason codes;
- candidate, evidence, authority, and governed-rule hashes;
- unresolved burdens and reopening conditions;
- retained and resolved typed failures;
- optional replay audit;
- explicit authority and ontology non-claims.

Malformed JSON receives an `INVALID` receipt based on the raw UTF-8 byte hash, without an inferred candidate status.

## Canonical JSON and replay

Canonical JSON is UTF-8; object keys sort lexicographically by Unicode code point; arrays preserve order; whitespace is removed; non-ASCII remains UTF-8; JSON escaping is minimal; nulls remain explicit; enums use uppercase values; timestamps normalize to UTC whole seconds ending in `Z`; and decimals are fixed-notation JSON strings with at most six fractional places. Duplicate keys, non-finite values, exponent notation, negative zero, excess precision, and binary floats in fixed-decimal fields are invalid.

Canonical serialization plus deterministic rules produces deterministic replay. Hashes identify canonical packets, decisions, and receipts and provide tamper evidence; they are not the source of determinism.

## Test design

The suite covers:

- exact seven-status vocabulary and separation from attempt outcomes;
- allowed adjacent routes, blocked jumps, terminal expiry, and anti-backflow;
- authorized commitment plus missing actor or rule-adoption authority;
- rule-hash tampering, candidate tampering, malformed JSON, duplicate keys, and binary floats;
- evidence/candidate receipt hashes and no lifecycle mutation on blocked/invalid attempts;
- deterministic receipt identity and explicit replay audit;
- baseline and profile-dependent unresolved expiry;
- typed reopening deltas, unmatched categories, and removal of corrected procedural contamination.

## Explicit ambiguity register

1. The seven statuses remain a proposed baseline, not a universal final taxonomy.
2. No universal weighting formula, factor list, threshold, or veto vocabulary is asserted.
3. “Substantially similar candidate” is not inferred heuristically; only explicit identity and lineage are handled.
4. Authority change is the minimal source-derived recheck trigger; other triggers remain profile work.
5. `MEASURED` remains purpose- and method-relative and does not mean objectively true.
6. Whether a declared unresolved burden may coexist with commitment is governed-rule-specific.
7. Expiry ends declared active eligibility, not historical trace or unresolved possibility itself.
8. The prototype validates declared authority packets, not their real-world truth or legitimacy.
9. Reopening by a new candidate reconciles dependency-sensitive reopening with anti-backflow, but broader certificate-validity semantics remain outside this prototype.
10. No mathematical ZSA definitions or theorems are implemented; only the attributed bookkeeping role scoped by the A0 Boundary Kernel source is modeled.
