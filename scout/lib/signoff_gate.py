"""Semantic Scout engine sign-off (universal — not tied to any ticket id)."""
from __future__ import annotations

from lib.deliverables import infer_deliverable_globs, primary_artifact_glob
from lib.jira_requirement_matrix import build_requirement_matrix, format_matrix_markdown
from lib.rdl_checks import country_column_first_ok
from lib.requirement_evidence import evaluate_requirement


def run_matrix_pattern_smoke() -> tuple[bool, str]:
    matrix = build_requirement_matrix(
        ticket_key="SCOUT-SMOKE",
        summary="Fix export - Revenue Analysis (paginated)",
        description="Acceptance criteria:\n- Remove trailing blank page on PDF export\n",
    )
    if not matrix:
        return False, "matrix empty"
    if any("country_filter" in row.automated_check_ids for row in matrix):
        return False, "unrelated ticket bound to country_filter"
    return True, f"generic matrix ({len(matrix)} rows)"


def run_deliverable_infer_smoke() -> tuple[bool, str]:
    globs = infer_deliverable_globs(
        "Add filter - New Members - Details (paginated)",
        "Also update semantic model measures",
    )
    if "**/New Members - Details.rdl" not in globs:
        return False, f"missing paginated glob: {globs}"
    if not any("tmdl" in g.lower() for g in globs):
        return False, f"missing model glob: {globs}"
    primary = primary_artifact_glob(globs)
    if not primary:
        return False, "no primary glob"
    return True, f"inferred {len(globs)} globs"


def run_country_column_rdl_smoke() -> tuple[bool, str]:
    mini = """
    <Tablix Name="Tablix1"><TablixBody><TablixRows><TablixRow>
    <Value>Country</Value><Value>=Fields!country.Value</Value>
    </TablixRow></TablixRows></TablixBody></Tablix>
    """
    return (
        (True, "country column heuristic OK")
        if country_column_first_ok(mini)
        else (False, "country column heuristic failed")
    )


def run_requirement_eval_smoke() -> tuple[bool, str]:
    status, _ = evaluate_requirement(
        {"id": "manual_SCOUT-01", "text": "Remove trailing blank page on PDF"},
        artifacts=[],
        checks={},
        changed_paths=[],
        diff_excerpt="",
    )
    return (
        (True, "evaluator OK")
        if status == "missing"
        else (False, f"expected missing, got {status}")
    )


def run_signoff_checks() -> dict:
    checks = [
        ("universal_matrix", run_matrix_pattern_smoke),
        ("deliverable_inference", run_deliverable_infer_smoke),
        ("country_column_heuristic", run_country_column_rdl_smoke),
        ("requirement_evaluator", run_requirement_eval_smoke),
    ]
    lines: list[str] = []
    all_ok = True
    for name, fn in checks:
        ok, detail = fn()
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        all_ok = all_ok and ok
    return {
        "ok": all_ok,
        "detail": "\n".join(lines),
        "message": "Scout universal engine ready" if all_ok else "Scout engine blocked",
    }


def main() -> int:
    result = run_signoff_checks()
    print("SEMANTIC SCOUT — ENGINE SIGN-OFF (universal)")
    print("=" * 40)
    print(result["detail"])
    print()
    print(result["message"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
