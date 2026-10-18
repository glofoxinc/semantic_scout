"""Semantic Scout install / engine sign-off (not ticket sign-off)."""

from __future__ import annotations

from pathlib import Path

from lib.jira_requirement_matrix import (
    build_requirement_matrix,
    format_matrix_markdown,
    infer_artifact_glob_from_summary,
)
from lib.requirement_evidence import evaluate_requirement


def run_matrix_country_smoke() -> tuple[bool, str]:
    matrix = build_requirement_matrix(
        ticket_key="AN-5605",
        summary="Add Country filter and column - New Members - Details (paginated)",
        description=(
            "Acceptance criteria:\n"
            "- Add Country filter on paginated report\n"
            "- Country as the first column\n"
            "- All countries selected by default\n"
            "- Documentation explains Country filter\n"
        ),
    )
    if len(matrix) < 3:
        return False, "matrix row count < 3"
    ids = {c for row in matrix for c in row.automated_check_ids}
    needed = {"country_filter", "country_column_first", "default_all_countries", "doc_country_filter"}
    if not needed <= ids:
        return False, f"missing check ids: {needed - ids}"
    md = format_matrix_markdown("AN-5605", "summary", matrix)
    if "How to verify" not in md:
        return False, "matrix markdown missing verify column"
    return True, f"country bundle matrix OK ({len(matrix)} rows)"


def run_matrix_generic_smoke() -> tuple[bool, str]:
    matrix = build_requirement_matrix(
        ticket_key="AN-TEST",
        summary="Fix blank page on Revenue Analysis paginated export",
        description="Acceptance criteria:\n- Remove trailing blank page on PDF export\n",
    )
    if not matrix:
        return False, "generic matrix empty"
    if any(row.automated_check_ids == ["country_filter"] for row in matrix):
        return False, "generic ticket wrongly bound to country_filter"
    return True, f"generic matrix OK ({len(matrix)} rows, no country auto-bind)"


def run_country_column_rdl_smoke() -> tuple[bool, str]:
    from lib.rdl_checks import country_column_first_ok

    mini = """
    <Tablix Name="Tablix1"><TablixBody><TablixRows><TablixRow>
    <Textbox><Value>Country</Value></Textbox>
    <Textbox><Value>=Fields!country.Value</Value></Textbox>
    </TablixRow></TablixRows></TablixBody></Tablix>
    """
    if not country_column_first_ok(mini):
        return False, "mini RDL country column check failed"
    prod = Path(
        r"C:\Users\LYal01\gf-insights-fitnessbi\New Members - Details.PaginatedReport\New Members - Details.rdl"
    )
    if prod.is_file():
        if not country_column_first_ok(prod.read_text(encoding="utf-8-sig")):
            return False, "New Members - Details.rdl failed country_column_first_ok"
        return True, "mini + production New Members column OK"
    return True, "mini RDL OK (production path not on machine)"


def run_artifact_glob_smoke() -> tuple[bool, str]:
    g = infer_artifact_glob_from_summary(
        "Add Country filter and column - New Members - Details (paginated)",
    )
    if g != "**/New Members - Details.rdl":
        return False, f"infer glob wrong: {g}"
    return True, g


def run_requirement_eval_smoke() -> tuple[bool, str]:
    """Manual row stays unverified without diff; country ids use structured checks."""
    status, _ = evaluate_requirement(
        {"id": "manual_AN-TEST-REQ-01", "text": "Remove trailing blank page on PDF"},
        artifacts=[],
        checks={},
        changed_paths=[],
        diff_excerpt="",
    )
    if status != "missing":
        return False, f"expected missing without artifact, got {status}"
    return True, "requirement evaluator smoke OK"


def run_signoff_checks() -> dict:
    lines: list[str] = []
    all_ok = True
    for name, fn in (
        ("country_ticket_matrix", run_matrix_country_smoke),
        ("generic_ticket_matrix", run_matrix_generic_smoke),
        ("country_column_rdl", run_country_column_rdl_smoke),
        ("artifact_glob_infer", run_artifact_glob_smoke),
        ("requirement_evaluator", run_requirement_eval_smoke),
    ):
        ok, detail = fn()
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        all_ok = all_ok and ok
    return {
        "ok": all_ok,
        "detail": "\n".join(lines),
        "message": "Scout engine ready" if all_ok else "Scout engine blocked — fix failures",
    }


def main() -> int:
    result = run_signoff_checks()
    print("SEMANTIC SCOUT — ENGINE SIGN-OFF")
    print("=" * 40)
    print(result["detail"])
    print()
    print(result["message"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
