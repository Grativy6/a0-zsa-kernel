# Provenance and claim boundary

## Ownership and attribution

Christopher D. Pang is the repository owner and the author and steward of the
A0/Software Boundary-Layer Kernel material. AI systems are implementation and
review tools, not co-authors, owners, adopters, grant issuers, or authorities.

Where ZSA or Infinity-Measurement Boundary material is referenced, that work
remains attributed to Lawrence Ip. This repository does not claim ZSA
authorship or conformance.

## Frozen references

| Item | Frozen identity | Status carried here |
|---|---|---|
| Legacy `Grativy6/a0-zsa-kernel` implementation | Commit `eb3505968a1b8a370862ce48f9f486b22a50cb17` | Frozen v0.1 implementation provenance; not rewritten by the routing profile |
| A0/Software Boundary-Layer Kernel v0.10.0 candidate | SHA-256 `f3b57da98db3b105e6a67b2c76471123365041ce86e53977be5aa7002b84c46a` | Proposed candidate source; not adopted or published by this implementation |
| A0_ZSA_Doom Build 008 final commit | `bbffd0be7d6d8b3a31f0c280632a52716bdd5ddd` | Evidence and adversarial-design provenance only |
| Build 008 packet seal | `2f61e3196bee35171c910c152b53b84fbff0be98e273808569647a35c7c46215` | Frozen packet identity; not regenerated here |
| Build 008 disposition | `PARTIAL` | Preserved without promotion |

Build 008 reported repository-local compatibility `PASS`, pinned-kernel
native SUCCESSOR support `OPEN`, and terminal reason
`PINNED_KERNEL_NATIVE_SUCCESSOR_UNRESOLVED`. Adding new interfaces in a later
revision does not retroactively alter that pinned commit, evidence packet,
test result, or disposition. This repository does not rerun or consume the
Build 008 sealed holdout.

The current work is best described as an independent implementation of
selected A0BK v0.10.0 candidate mechanisms informed by the frozen evidence.
Reference identities are provenance, not proof, adoption, authority, or a
code-reuse grant. Any copied or adapted third-party material must retain its
own source and license record.

## Separate version identities

Document version, schema version, package version, Git revision, policy
version, run identity, and deployed configuration are separate identifiers.
No value may be inferred from another. In particular, a package or policy
using `0.10.0` as a source-version reference does not declare that the source
document has been adopted or that the package is conformant.

## Public visibility and licensing

At the time this notice was written, the repository has no operative root
`LICENSE`. Public visibility makes the repository inspectable; it does not by
itself grant permission to copy, modify, redistribute, sublicense, or deploy
the code. Applicable law may provide limited rights independently. If an
operative license is later added by the owner, that license controls according
to its terms from its stated scope and effective revision.

No license should be inferred from a source hash, attribution, public URL,
test result, pull request, successful run, or this provenance notice.

## Bounded implementation statement

The defensible profile-level statement is:

> A deterministic, offline, shadow-only implementation of selected A0BK
> v0.10.0 candidate routing mechanisms, with Strongwiz-facing proposal models
> and Build 008-informed provenance and adversarial boundaries.

This statement does not claim complete A0BK, PAL, ZSA, FBT, PECAN, A12,
security, authority, execution, contest readiness, or performance benefit.

