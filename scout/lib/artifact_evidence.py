"""Structured evidence for dashboard (report.json) and semantic model (.tmdl) artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _path_in_diff(changed_paths: list[str], artifact: Path) -> bool:
    name = artifact.name.lower()
    rel_hint = str(artifact).replace("\\", "/").lower()
    for p in changed_paths:
        pl = p.replace("\\", "/").lower()
        if name in pl or pl.endswith(name) or rel_hint.endswith(pl):
            return True
    return False


def analyze_dashboard_artifact(
    path: Path,
    *,
    changed_paths: list[str],
    diff_excerpt: str,
) -> dict[str, bool]:
    checks: dict[str, bool] = {"dashboard_file_present": path.is_file()}
    if not checks["dashboard_file_present"]:
        return checks
    try:
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        checks["dashboard_json_valid"] = False
        return checks
    checks["dashboard_json_valid"] = True
    checks["dashboard_in_diff"] = _path_in_diff(changed_paths, path) if changed_paths else True
    blob = raw.lower()
    checks["documentation_page_in_report"] = (
        "measures and definitions" in blob
        or "documentation" in blob
        and "displayname" in blob
    )
    checks["has_visuals"] = bool(data.get("sections") or data.get("visualContainers"))
    inv = str(data.get("isInvertedSelectionMode", "")).lower()
    checks["location_slicer_inverted_mode_set"] = "isInvertedSelectionMode" in raw
    if "documentation" in diff_excerpt.lower() and path.name.lower() == "report.json":
        checks["documentation_touched_in_diff"] = True
    else:
        checks["documentation_touched_in_diff"] = "documentation" in diff_excerpt.lower() and checks[
            "dashboard_in_diff"
        ]
    return checks


def analyze_tmdl_artifact(
    path: Path,
    *,
    changed_paths: list[str],
    diff_excerpt: str,
) -> dict[str, bool]:
    checks: dict[str, bool] = {"tmdl_file_present": path.is_file()}
    if not checks["tmdl_file_present"]:
        return checks
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        checks["tmdl_readable"] = False
        return checks
    checks["tmdl_readable"] = True
    checks["tmdl_in_diff"] = _path_in_diff(changed_paths, path) if changed_paths else True
    checks["tmdl_has_measure"] = bool(re.search(r"^\s*measure\s+", text, re.I | re.M))
    checks["tmdl_has_table"] = bool(re.search(r"^\s*table\s+", text, re.I | re.M))
    name = path.stem.lower()
    checks["tmdl_touched_in_diff"] = name in diff_excerpt.lower() or checks["tmdl_in_diff"]
    return checks


def merge_check_dicts(base: dict[str, bool], extra: dict[str, bool]) -> dict[str, bool]:
    out = dict(base)
    for k, v in extra.items():
        out[k] = bool(out.get(k)) and v if k in out else v
    return out


def build_non_rdl_checks(
    artifacts: list[Path],
    *,
    changed_paths: list[str],
    diff_excerpt: str,
) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for path in artifacts:
        low = str(path).replace("\\", "/").lower()
        if path.name.lower() == "report.json" or ".report/" in low:
            checks = merge_check_dicts(
                checks,
                analyze_dashboard_artifact(
                    path, changed_paths=changed_paths, diff_excerpt=diff_excerpt
                ),
            )
        elif path.suffix.lower() == ".tmdl":
            checks = merge_check_dicts(
                checks,
                analyze_tmdl_artifact(
                    path, changed_paths=changed_paths, diff_excerpt=diff_excerpt
                ),
            )
    return checks
