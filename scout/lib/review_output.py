"""Structured Scout review payload for agents and MCP."""
from __future__ import annotations

from typing import Any

from lib.bot_resolution import build_bot_resolution_checklist, format_bot_resolution_md
from lib.git_scope import format_scope_report


def build_review_summary(
    *,
    ticket_key: str,
    matrix_markdown: str,
    scope_violations: list[dict[str, str]],
    bot_predictions: list[dict[str, Any]],
    reports: list[Any],
    changed_paths: list[str],
    circuit_stale: bool = False,
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
    return {
        "ticket_key": ticket_key,
        "changed_paths_count": len(changed_paths),
        "ratings": {
            "jira": rep.jira_rating if rep else 0,
            "delivery": rep.delivery_rating if rep else 0,
            "standards": rep.standards_rating if rep else -1,
            "combined": rep.combined_rating if rep else 0,
            "ready_mcp": rep.ready_for_pr if rep else False,
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
            "READY for PR only after agent verifies each must_have row with a file path "
            "and bot checklist items are done or waived in chat."
        ),
    }
