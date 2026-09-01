# Strongwiz shadow-routing profile

## Status

`strongwiz-shadow-v0.1` is a deterministic, advisory-only profile for testing
whether selected A0BK v0.10.0 candidate distinctions improve the routing of
Strongwiz proposals. It is not an executor, an autonomous Kaggle agent, an
authority source, a PAL closure mechanism, or a claim of complete A0BK
conformance.

The profile is deliberately narrower than A0BK v0.10.0. It exercises a
selected W0-W6 route over eight project guards. It does not separately
implement the candidate document's complete ten-guard registry, a trusted
host authority boundary, a PECAN crossing, an executor, or the optional
composite/FBT profile.

## Roles and separation

Strongwiz belongs to the proposal plane. It may supply candidate actions,
targets, predicted consequences, meaningful distinctions, decision effects,
evidence references, uncertainty, costs, residual references, and material
deltas. It must not manufacture policy, trusted identity, grant validity,
revocation state, trusted time, budgets, or serial-token state.

The control plane is represented by a separate, strict `ControlSnapshot`.
It supplies the active account and observation bindings, available evidence
and trace references, resource budgets, the declared grant snapshot, the
serial token, and the exact `RouterPolicy`. Both models reject extra fields.
Placing the two values in one `RoutingRequest` transport envelope does not
merge their semantics or permit proposal fields to overwrite control fields.

This is currently structural separation, not a trusted-host guarantee. A
local caller can still construct a false `ControlSnapshot`; the profile checks
internal bindings, not real issuer identity, signatures, standing, trusted
time, revocation infrastructure, or human permission. A deployment that makes
stronger claims must construct and verify control data outside the
model-writable path.

## Decision relevance

A candidate names its `meaningful_distinction` and at least one typed
`decision_effect`. The available effects are plan, risk, candidate choice,
experiment choice, resource, access, hazard, and movement. Evidence,
conflicting evidence, active residuals, uncertainty, action cost, life cost,
reversibility, and consequence class remain separate fields.

The root and scoped goals bind relevance to the task chosen before routing.
For ARC play, the root goal may be an officially observed `GameState.WIN`,
while a new level surface supplies a new scoped goal. Previous mechanics may
remain evidence dependencies. A later contradiction should name the affected
account or residual and an exact material delta instead of silently rewriting
the earlier record.

`proposed_rank` is proposal data, not an earned result. A profile may compare
eligible candidates, but a rank, metric, score, confidence, or successful
outcome cannot repair a failed hard guard or create authority. The initial
profile configures no weighted diagnostic.

## Selected W0-W6 route

The selected profile uses these stages:

1. **W0 - Freeze.** Bind the proposal, control snapshot, active account and
   version, current observation, generator, policy, and serial token to stable
   hashes. An identity mismatch is held or rejected; it is not repaired by a
   later score.
2. **W1 - Witness.** Check that each candidate's evidence and any claimed
   material delta are present in the declared evidence aperture. Missing
   evidence returns `REQUEST_WITNESS` or leaves the route held.
3. **W2 - Hard guards.** Evaluate `IDENTITY`, `WITNESS`, `SCOPE`, `TRACE`,
   `AUTHORITY`, `CONSEQUENCE`, `RESOURCE`, and `REENTRY` independently as
   `PASS`, `FAIL`, `UNRESOLVED`, or `NOT_APPLICABLE`.
4. **W3 - Boundary.** Preserve the declared consequence class and the
   profile's nonexternal boundary. No domain adapter or consequential
   crossing is inferred.
5. **W4 - Diagnostics.** Apply a diagnostic only when the policy explicitly
   supplies one. `strongwiz-shadow-v0.1` supplies none, so diagnostic scoring
   is not an authority or admission path.
6. **W5 - Route.** Select one typed advisory disposition from `ADMIT`, `HOLD`,
   `REQUEST_WITNESS`, `REJECT`, or `REOPEN`.
7. **W6 - Return.** Return one deterministic `RouteDecision` with the stage
   and guard evidence, limitations, `nonexecution_marker=true`,
   `authority="NONE"`, and `effect="NONE"`.

The project `RESOURCE` guard is a Strongwiz experiment guard, not a substitute
for the candidate document's separately named `G-FLOOR`, `G-ADAPTER`, or
`G-DATA`. Their absence from this profile remains an explicit conformance
gap.

## Route meanings

- `ADMIT` means that one candidate is eligible for advisory consideration in
  the declared shadow aperture. It is not permission or execution.
- `HOLD` preserves an unresolved binding, guard, consequence, or resource
  condition.
- `REQUEST_WITNESS` asks the caller for specifically missing evidence.
- `REJECT` records a bounded policy refusal while preserving the proposal.
- `REOPEN` requires a prior account reference plus at least one material-delta
  reference. It does not edit the prior record, choose PAL A15 status, or
  automatically establish VERSION continuity.

No route invokes a game environment, connector, subprocess, network service,
credential, grant consumer, or external model. A later Hearthline integration
must keep a single environment writer and independently bind the exact action,
current observation, budget, and any required external authority.

## Claim ceiling

The profile may support a claim that selected A0BK-inspired guards produced a
deterministic advisory route for supplied fixtures. It cannot establish that:

- A0BK v0.10.0 was adopted, published, or implemented in full;
- the frozen Build 008 `PARTIAL` disposition became `PASS`;
- PAL, ZSA, FBT, A12, PECAN, or Strongwiz conformance was earned;
- the supplied evidence, control snapshot, or grant was true or legitimate;
- a route was ethical, lawful, safe, authorized, optimal, or executed;
- Strongwiz improved action efficiency or generalization; or
- the package is an autonomous offline Kaggle agent.
