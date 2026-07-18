from a0_zsa_kernel.enums import LifecycleStatus


def test_exact_source_baseline_statuses():
    assert [status.value for status in LifecycleStatus] == [
        "UNRESOLVED",
        "CANDIDATE",
        "WEIGHTED",
        "MEASURED",
        "COMMITTED",
        "REJECTED",
        "EXPIRED",
    ]
