"""MCP response shape contract (structured output)."""
from __future__ import annotations

import json
from pathlib import Path

from lib.review_output import build_review_summary
from lib.ticket_gap_report import TicketReport


def test_review_summary_has_required_v1_fields():
    rep = TicketReport(
        key="AN-100",
        summary="Test",
        artifact_path="x.rdl",
        jira_rating=95,
        delivery_rating=90,
        standards_rating=-1,
        branch_rating=90,
        combined_rating=92,
        ready_for_pr=True,
        verdict="CLEAR",
    )
    summary = build_review_summary(
        ticket_key="AN-100",
        matrix_markdown="| id | text |",
        scope_violations=[],
        bot_predictions=[],
        reports=[rep],
        changed_paths=["x.rdl"],
        engine_ok=True,
        branch_name="feature/AN-100",
        base_ref="origin/main",
        deliverable_globs=["**/x.rdl"],
    )
    required = {
        "readiness",
        "readiness_reasons",
        "confidence",
        "confidence_notes",
        "review_card_markdown",
        "ratings",
        "requirements",
    }
    assert required.issubset(summary.keys())
    assert summary["readiness"] in ("READY", "NOT READY")
    assert "SEMANTIC SCOUT REVIEW" in summary["review_card_markdown"]


def test_response_schema_file_exists():
    path = Path(__file__).resolve().parents[1] / "schema" / "ticket_review_response.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "scout_ticket_review" in data["title"] or "ticket_review" in data["title"]
