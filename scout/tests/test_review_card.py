"""Review card and readiness gate tests."""
from __future__ import annotations

from lib.review_card import (
    decide_readiness,
    format_review_card,
    validate_ticket_key,
)
from lib.ticket_gap_report import Gap, TicketReport


def test_validate_ticket_key():
    assert validate_ticket_key("an-1234")[0]
    assert validate_ticket_key("PIC-99")[0]
    assert not validate_ticket_key("XX-1")[0]


def test_readiness_not_ready_when_missing_ac():
    rep = TicketReport(
        key="AN-1",
        summary="t",
        artifact_path="foo.rdl",
        jira_rating=50,
        delivery_rating=50,
        standards_rating=-1,
        branch_rating=50,
        combined_rating=50,
        ready_for_pr=False,
        verdict="FIX_FIRST",
        requirements=[],
    )
    reqs = [{"text": "Add filter", "status": "missing", "must_have": True, "evidence": "none"}]
    status, reasons = decide_readiness(
        engine_ok=True,
        report=rep,
        requirements=reqs,
        scope_violations=[],
        bot_blocker_count=0,
    )
    assert status == "NOT READY"
    assert reasons


def test_review_card_contains_readiness_block():
    md = format_review_card(
        ticket_key="AN-1",
        branch_name="feature/AN-1-x",
        base_ref="origin/main",
        report=None,
        requirements=[{"text": "x", "status": "met", "evidence": "file.rdl"}],
        scope_violations=[],
        deliverable_globs=["**/x.rdl"],
        changed_paths=["a.rdl"],
        readiness="NOT READY",
        readiness_reasons=["test reason"],
        additional_findings=[],
    )
    assert "SEMANTIC SCOUT REVIEW" in md
    assert "Readiness gate" in md
    assert "NOT READY" in md
    assert "MET" in md
