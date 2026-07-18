from .enums import LifecycleStatus


BASELINE_TRANSITIONS: dict[LifecycleStatus, frozenset[LifecycleStatus]] = {
    LifecycleStatus.UNRESOLVED: frozenset({LifecycleStatus.CANDIDATE}),
    LifecycleStatus.CANDIDATE: frozenset(
        {LifecycleStatus.WEIGHTED, LifecycleStatus.REJECTED, LifecycleStatus.EXPIRED}
    ),
    LifecycleStatus.WEIGHTED: frozenset(
        {LifecycleStatus.MEASURED, LifecycleStatus.REJECTED, LifecycleStatus.EXPIRED}
    ),
    LifecycleStatus.MEASURED: frozenset(
        {LifecycleStatus.COMMITTED, LifecycleStatus.REJECTED, LifecycleStatus.EXPIRED}
    ),
    LifecycleStatus.COMMITTED: frozenset({LifecycleStatus.EXPIRED}),
    LifecycleStatus.REJECTED: frozenset({LifecycleStatus.EXPIRED}),
    LifecycleStatus.EXPIRED: frozenset(),
}


def route_allowed(
    source: LifecycleStatus,
    target: LifecycleStatus,
    *,
    allow_unresolved_expiry: bool,
) -> bool:
    if source is LifecycleStatus.UNRESOLVED and target is LifecycleStatus.EXPIRED:
        return allow_unresolved_expiry
    return target in BASELINE_TRANSITIONS[source]
