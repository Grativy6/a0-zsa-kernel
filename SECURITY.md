# Security policy

## Project status

This repository is an experimental, nondeployed prototype. It has no released
or formally supported security version, warranty, response-time commitment,
bug bounty, or claim of suitability for consequential use.

The Strongwiz profile is shadow-only. Expected output has
`nonexecution_marker=true`, `authority="NONE"`, and `effect="NONE"`. A route,
receipt, hash, passing test, or advisory admission must not cause an external
effect or be treated as permission.

## Relevant security findings

Please report defects that could cause or conceal:

- proposal data populating or overwriting control, policy, issuer, grant,
  trusted-time, revocation, budget, or serial-token fields;
- bypass of a hard guard or a diagnostic overriding one;
- direct execution, network access, credential use, or connector invocation;
- acceptance of stale or replayed lineage or multiple outputs from one live
  serial token;
- receipt, canonicalization, digest, account, residual, or SUCCESSOR identity
  confusion;
- mutation or loss of prior failure, refusal, residual, or reopening evidence;
- a TestReceipt or lifecycle result assigning PAL A15 closure;
- authority, safety, or conformance claims wider than the recorded evidence;
  or
- accidental disclosure of credentials, private data, sealed fixtures, or
  unrelated personal information.

## How to report

Do not place credentials, tokens, private data, sealed evidence, or working
exploit details in a public issue.

Use GitHub's private vulnerability-reporting facility from this repository's
Security tab if that facility is available. If it is not available, open a
minimal public issue stating only that a potentially sensitive security issue
exists and requesting a private reporting channel. Do not include the
sensitive details in that issue. This document intentionally does not invent
an email address, response team, encryption key, or external contact channel.

## Known limits

- `ProposalPacket` and `ControlSnapshot` are structurally separate, but the
  current local process does not establish a trusted host, issuer, clock,
  signature, revocation registry, standing, or real human authorization.
- The profile does not implement an executor or a one-use consequential grant
  consumer.
- Local deterministic validation is not proof of source truth, authenticity,
  security, privacy, safety, or deployment coverage.
- Serial behavior does not establish concurrent, distributed, or crash-safe
  authority conservation.
- The repository may retain evidence-rich records. A future deployment needs
  an explicit data classification, minimization, access, retention, deletion,
  and disclosure policy before processing sensitive material.
- Public repository visibility exposes tracked history. Secrets and sealed or
  private evidence must remain outside Git and should be scanned before every
  publication or release boundary.
