"""Run Paginate analyze_rdl_against_standards from Semantic Scout (local product path)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_PRODUCT = (
    Path(__file__).resolve().parents[3]
    / "paginate-platform"
    / "workspace"
    / "product"
)


def run_paginate_full_audit(
    rdl_path: Path,
    jira_key: str,
    *,
    product_root: Path | None = None,
) -> dict[str, Any]:
    root = product_root or Path(os.environ.get("PAGINATE_PRODUCT_ROOT", str(_DEFAULT_PRODUCT)))
    if not root.is_dir():
        return {"ok": False, "error": f"Paginate product root not found: {root}"}

    import sys

    platform_root = str(root.parent.parent)
    product_str = str(root)
    for entry in (platform_root, product_str):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    from paginate.mcp.flat_tools import analyze_rdl_against_standards

    raw = analyze_rdl_against_standards(
        str(rdl_path),
        profile="full",
        jira_key=jira_key,
        response_format="json",
    )
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)
