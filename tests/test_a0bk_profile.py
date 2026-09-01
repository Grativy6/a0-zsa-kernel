from __future__ import annotations

import ast
import json
from pathlib import Path

from a0bk_kernel.models import GuardId, RouterMode, RouterPolicy

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_strongwiz_profile_is_strict_and_shadow_only() -> None:
    raw = (ROOT / "profiles" / "strongwiz-shadow-v0.1.json").read_text(encoding="utf-8")
    policy = RouterPolicy.model_validate(json.loads(raw))
    assert policy.mode is RouterMode.SHADOW_ONLY
    assert policy.diagnostic is None
    assert policy.allow_external_proposals is False
    assert {item.guard_id for item in policy.guards} == set(GuardId)
    assert all(
        item.authority_ceiling == "NO_EXECUTION_AUTHORITY" for item in policy.guards
    )


def test_router_module_has_no_executor_or_network_import() -> None:
    source = (ROOT / "src" / "a0bk_kernel" / "routing.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                alias.name.split(".", maxsplit=1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", maxsplit=1)[0])
    assert imported.isdisjoint(
        {
            "httpx",
            "openai",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
    )
