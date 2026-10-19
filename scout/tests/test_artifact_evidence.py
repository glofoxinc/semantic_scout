"""Dashboard and TMDL evidence checks."""
from __future__ import annotations

import json
from pathlib import Path

from lib.artifact_evidence import analyze_dashboard_artifact, analyze_tmdl_artifact


def test_dashboard_json_checks(tmp_path: Path):
    report_dir = tmp_path / "Foo.Report"
    report_dir.mkdir()
    path = report_dir / "report.json"
    path.write_text(
        json.dumps({"sections": [{"name": "Measures and Definitions"}]}),
        encoding="utf-8",
    )
    checks = analyze_dashboard_artifact(
        path,
        changed_paths=[f"Foo.Report/report.json"],
        diff_excerpt="",
    )
    assert checks["dashboard_json_valid"]
    assert checks["documentation_page_in_report"]


def test_tmdl_checks(tmp_path: Path):
    path = tmp_path / "Model.tmdl"
    path.write_text("table Sales\n\tcolumn Amount\nmeasure Revenue = SUM(Sales[Amount])\n", encoding="utf-8")
    checks = analyze_tmdl_artifact(
        path,
        changed_paths=["Model.tmdl"],
        diff_excerpt="measure Revenue",
    )
    assert checks["tmdl_has_measure"]
    assert checks["tmdl_in_diff"]
