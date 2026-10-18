"""Map bot preflight hits to fix + re-verify steps (Semantic Scout)."""
from __future__ import annotations

from typing import Any


def build_bot_resolution_checklist(
    predictions: list[dict[str, Any]],
    *,
    circuit_stale: bool = False,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if circuit_stale:
        items.append(
            {
                "priority": "1",
                "bot": "Circuit",
                "action": "Comment /circuit review on latest commit or re-request review",
                "verify": "circuit_reviewed_sha equals head_sha",
            }
        )
    for idx, p in enumerate(predictions, start=len(items) + 1):
        score = float(p.get("score") or 0)
        if score < 3.0:
            continue
        items.append(
            {
                "priority": str(idx),
                "bot": ", ".join(p.get("bot_sources") or ["review bot"]),
                "action": p.get("do_before_opening_pr") or "Address before opening PR",
                "verify": f"Re-run scout_ticket_review; prediction score was {score}",
                "finding": p.get("likely_bot_finding") or "",
            }
        )
    return items


def format_bot_resolution_md(checklist: list[dict[str, str]]) -> str:
    if not checklist:
        return "BOT RESOLUTION: no high-confidence bot risks flagged."
    lines = ["BOT RESOLUTION CHECKLIST (fix before PR):"]
    for row in checklist:
        lines.append(f"  {row['priority']}. [{row['bot']}] {row.get('finding', '')}")
        lines.append(f"     Action: {row['action']}")
        lines.append(f"     Verify: {row['verify']}")
    return "\n".join(lines)
