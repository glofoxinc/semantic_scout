"""Structured Scout review payload for agents and MCP."""
from __future__ import annotations

from typing import Any

from lib.bot_resolution import build_bot_resolution_checklist, format_bot_resolution_md
from lib.git_scope import format_scope_report
from lib.review_card import (
    build_additional_findings,
    compute_confidence,
    decide_readiness,
    format_review_card,
)


def build_review_summary(
    *,
    ticket_key: str,
    matrix_markdown: str,
    scope_violations: list[dict[str, str]],
    bot_predictions: list[dict[str, Any]],
    reports: list[Any],
    changed_paths: list[str],
    circuit_stale: bool = False,
    engine_ok: bool = True,
    branch_name: str = "",
    base_ref: str = "origin/main",
    deliverable_globs: list[str] | None = None,
    jira_confidence_notes: list[str] | None = None,
) -> dict[str, Any]:
    rep = reports[0] if reports else None
    checklist = build_bot_resolution_checklist(
        bot_predictions, circuit_stale=circuit_stale
    )
    requirements = []
    if rep:
        for r in rep.requirements:
            requirements.append(
                {
                    "id": r.req_id,
                    "text": r.text,
                    "status": r.status,
                    "evidence": r.evidence,
                    "must_have": r.must_have,
                    "agent_must_read_file": r.status in ("met", "partial")
                    and "manual" not in r.req_id,
                }
            )
    bot_blockers = [
        g for g in (rep.gaps if rep else []) if g.kind == "bot" and g.severity == "blocker"
    ]
    readiness, readiness_reasons = decide_readiness(
        engine_ok=engine_ok,
        report=rep,
        requirements=requirements,
        scope_violations=scope_violations,
        bot_blocker_count=len(bot_blockers),
    )
    confidence, confidence_notes = compute_confidence(
        engine_ok=engine_ok,
        jira_notes=jira_confidence_notes or [],
        changed_paths_count=len(changed_paths),
        requirements=requirements,
        readiness=readiness,
    )
    extra = build_additional_findings(rep, bot_predictions)
    review_card_markdown = format_review_card(
        ticket_key=ticket_key,
        branch_name=branch_name,
        base_ref=base_ref,
        report=rep,
        requirements=requirements,
        scope_violations=scope_violations,
        deliverable_globs=deliverable_globs or [],
        changed_paths=changed_paths,
        readiness=readiness,
        readiness_reasons=readiness_reasons,
        additional_findings=extra,
    )
    return {
        "ticket_key": ticket_key,
        "branch_name": branch_name,
        "base_ref": base_ref,
        "changed_paths_count": len(changed_paths),
        "readiness": readiness,
        "readiness_reasons": readiness_reasons,
        "confidence": confidence,
        "confidence_notes": confidence_notes,
        "review_card_markdown": review_card_markdown,
        "ratings": {
            "jira_coverage": rep.jira_rating if rep else 0,
            "branch_hygiene": rep.branch_rating if rep else 0,
            "delivery": rep.delivery_rating if rep else 0,
            "standards": rep.standards_rating if rep else -1,
            "combined": rep.combined_rating if rep else 0,
            "jira": rep.jira_rating if rep else 0,
            "ready_mcp": readiness == "READY",
            "ready_bot_clear": len(bot_blockers) == 0,
            "verdict": rep.verdict if rep else "FIX_FIRST",
        },
        "requirements": requirements,
        "scope_report": format_scope_report(scope_violations),
        "bot_ahead_count": len(bot_predictions),
        "bot_resolution_checklist": checklist,
        "bot_resolution_markdown": format_bot_resolution_md(checklist),
        "matrix_markdown": matrix_markdown,
        "human_gate": (
            "Open PR only when readiness is READY. If confidence is medium/low, "
            "re-read flagged files or paste fuller Jira text, then re-run Scout."
        ),
    }
