"""Canonical Semantic Scout review card (REQUIREMENTS.md §4) + readiness gate."""
from __future__ import annotations

import re
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]
Readiness = Literal["READY", "NOT READY"]

_TICKET_KEY_RE = re.compile(r"^(AN|PIC)-\d+$", re.IGNORECASE)


def validate_ticket_key(ticket_key: str) -> tuple[bool, str]:
    key = (ticket_key or "").strip().upper()
    if not key:
        return False, "Ticket key is empty"
    if not _TICKET_KEY_RE.match(key):
        return False, "Ticket key must be AN-#### or PIC-####"
    return True, key


def validate_jira_payload(
    summary: str, description: str, comments_text: str
) -> list[str]:
    """Warnings that lower confidence — not hard errors."""
    notes: list[str] = []
    body = f"{summary}\n{description}\n{comments_text}".strip()
    if len(body) < 40:
        notes.append("Jira text is very short — paste full description and AC in the MCP call")
    if not (description or "").strip():
        notes.append("No description passed — acceptance criteria may be incomplete")
    return notes


def _status_label(status: str) -> str:
    mapping = {
        "met": "MET",
        "missing": "MISSING",
        "partial": "PARTIAL",
        "unverified": "UNVERIFIED",
    }
    return mapping.get(status, status.upper())


def decide_readiness(
    *,
    engine_ok: bool,
    report: Any | None,
    requirements: list[dict[str, Any]],
    scope_violations: list[dict[str, str]],
    bot_blocker_count: int,
) -> tuple[Readiness, list[str]]:
    reasons: list[str] = []
    if not engine_ok:
        reasons.append("Scout engine sign-off failed — run scout_engine_health and fix install")

    if report is None:
        reasons.append("No ticket report produced — check Jira text and repo path")
        return "NOT READY", reasons

    if not (getattr(report, "artifact_path", None) or "").strip():
        reasons.append("Primary deliverable file not found in repo for this ticket")

    for row in requirements:
        if not row.get("must_have", True):
            continue
        st = row.get("status", "missing")
        if st == "missing":
            reasons.append(f"MISSING AC: {row.get('text', '')[:120]}")
        elif st == "partial":
            reasons.append(f"PARTIAL AC (not sufficient for READY): {row.get('text', '')[:120]}")
        elif st == "unverified":
            reasons.append(f"UNVERIFIED AC — confirm manually: {row.get('text', '')[:120]}")

    for v in scope_violations:
        if v.get("severity") == "blocker":
            reasons.append(f"Scope blocker: {v.get('path')} — {v.get('reason')}")

    if bot_blocker_count > 0:
        reasons.append(
            f"{bot_blocker_count} predicted bot blocker(s) — resolve or waive in chat before PR"
        )

    jira = int(getattr(report, "jira_rating", 0) or 0)
    delivery = int(getattr(report, "delivery_rating", 0) or 0)
    if jira < 90:
        reasons.append(f"Jira coverage below 90 ({jira}/100)")
    if delivery < 85:
        reasons.append(f"Branch delivery score below 85 ({delivery}/100)")

    if not getattr(report, "ready_for_pr", False) and not any(
        "coverage below" in r or "delivery score" in r for r in reasons
    ):
        reasons.append("Internal ready gate failed — see gaps and requirements")

    if reasons:
        return "NOT READY", reasons
    return "READY", ["All mandatory checks passed for this scan"]


def compute_confidence(
    *,
    engine_ok: bool,
    jira_notes: list[str],
    changed_paths_count: int,
    requirements: list[dict[str, Any]],
    readiness: Readiness,
) -> tuple[Confidence, list[str]]:
    notes = list(jira_notes)
    if not engine_ok:
        return "low", notes + ["Engine health failed"]
    if changed_paths_count == 0:
        notes.append("No files changed vs base — diff may be wrong branch or base_ref")
    unverified = sum(1 for r in requirements if r.get("status") == "unverified")
    partial = sum(1 for r in requirements if r.get("status") == "partial")
    if unverified or partial:
        notes.append(f"{unverified} unverified and {partial} partial criteria in this scan")
    if readiness == "NOT READY":
        return "medium" if changed_paths_count > 0 else "low", notes
    if jira_notes or unverified:
        return "medium", notes
    return "high", notes


def format_review_card(
    *,
    ticket_key: str,
    branch_name: str,
    base_ref: str,
    report: Any | None,
    requirements: list[dict[str, Any]],
    scope_violations: list[dict[str, str]],
    deliverable_globs: list[str],
    changed_paths: list[str],
    readiness: Readiness,
    readiness_reasons: list[str],
    additional_findings: list[str],
) -> str:
    jira_score = getattr(report, "jira_rating", 0) if report else 0
    branch_score = getattr(report, "branch_rating", 0) if report else 0
    if branch_score == 0 and report:
        branch_score = getattr(report, "delivery_rating", 0)

    lines: list[str] = [
        "SEMANTIC SCOUT REVIEW",
        f"Ticket: {ticket_key} · Branch: {branch_name or '(unknown)'} · Base: {base_ref}",
        "",
        f"Jira coverage      — {jira_score}/100  (from criteria evidence)",
        f"Branch hygiene     — {branch_score}/100  (from branch checks)",
        "",
    ]
    if deliverable_globs:
        lines.append("Expected artifacts (inferred)")
        for g in deliverable_globs[:8]:
            lines.append(f"  · {g}")
        lines.append("")

    lines.append("Acceptance criteria")
    if not requirements:
        lines.append("  (no criteria parsed — improve Jira description or paste AC)")
    else:
        for row in requirements:
            label = _status_label(str(row.get("status", "missing")))
            text = row.get("text", "").strip() or row.get("id", "")
            evidence = (row.get("evidence") or "no evidence recorded").strip()
            lines.append(f"  {label:<10} — {text}")
            lines.append(f"             Evidence: {evidence}")
    lines.append("")
    lines.append("Additional findings")
    if scope_violations:
        for v in scope_violations:
            sev = v.get("severity", "info")
            lines.append(f"  · [{sev}] {v.get('path')}: {v.get('reason')}")
    else:
        lines.append("  · No scope violations flagged")
    for finding in additional_findings:
        lines.append(f"  · {finding}")
    if report and getattr(report, "gaps", None):
        for g in report.gaps[:12]:
            if g.kind == "bot":
                continue
            lines.append(f"  · ({g.kind}) {g.issue}")
    if changed_paths:
        lines.append(f"  · {len(changed_paths)} path(s) changed on branch")
    lines.append("")
    lines.append("Readiness gate")
    lines.append(f"  {readiness}")
    for reason in readiness_reasons[:15]:
        lines.append(f"  — {reason}")
    lines.append("")
    lines.append(
        "(Calculated from live Jira text and git diff. Re-run after fixes: Semantic Scout for "
        f"{ticket_key})"
    )
    return "\n".join(lines)


def build_additional_findings(
    report: Any | None,
    bot_predictions: list[dict[str, Any]],
) -> list[str]:
    out: list[str] = []
    if report:
        for g in getattr(report, "gaps", []) or []:
            if g.kind == "bot" and g.severity in ("blocker", "gap"):
                out.append(f"Bot-ahead: {g.issue}")
    for pred in bot_predictions[:5]:
        msg = pred.get("message") or pred.get("issue") or str(pred)
        if msg:
            out.append(f"Likely review feedback: {msg}")
    return out
