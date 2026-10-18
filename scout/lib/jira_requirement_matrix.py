"""Parse Jira text into a numbered requirement matrix with concrete verification hints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

RequirementCategory = Literal[
    "filter",
    "column",
    "documentation",
    "layout",
    "scope",
    "parity",
    "process",
    "generic",
]

_SCOPE_SECTION = re.compile(
    r"(?im)^(?:#+\s*)?"
    r"(acceptance\s+criteria|testing\s+checklist|requirements|deliverables|scope|"
    r"out\s+of\s+scope|definition\s+of\s+done)"
    r"\s*:?\s*$"
)
_BULLET = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+(.+)$")
_OUT_OF_SCOPE = re.compile(r"(?i)out\s+of\s+scope|not\s+in\s+scope|paginated\s+only|no\s+dashboard")


@dataclass
class MatrixRequirement:
    req_id: str
    text: str
    source: str
    category: RequirementCategory
    in_scope: bool
    verify_hint: str
    automated_check_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "text": self.text,
            "source": self.source,
            "category": self.category,
            "in_scope": self.in_scope,
            "verify_hint": self.verify_hint,
            "automated_check_ids": self.automated_check_ids,
        }


def _classify(text: str) -> RequirementCategory:
    low = text.lower()
    if _OUT_OF_SCOPE.search(low):
        return "scope"
    if "country" in low or "filter" in low or "parameter" in low or "branch" in low:
        return "filter"
    if "first column" in low or "column" in low or "grid" in low:
        return "column"
    if "document" in low or "doc page" in low:
        return "documentation"
    if "dashboard" in low and "paginated" in low:
        return "parity"
    if "pbix" in low or ".tmdl" in low or "semantic model" in low:
        return "parity"
    return "generic"


def _checks_for_text(text: str, category: RequirementCategory) -> tuple[str, list[str]]:
    low = text.lower()
    if "document" in low and "country" in low:
        return (
            "DocumentationPage: branch country (not member home); all countries default.",
            ["doc_country_filter"],
        )
    if "country" in low and "filter" in low:
        return (
            "Open target .rdl: ReportParameter Name=Country (MultiValue); "
            "dataset prm_Country; MainQuery uses IN (@Country).",
            ["country_filter"],
        )
    if "country" in low and ("first column" in low or ("first" in low and "column" in low)):
        return (
            "First tablix header row must be Country; Fields!country or equivalent first detail cell.",
            ["country_column_first"],
        )
    if (
        "all countries" in low
        or "countries selected" in low
        or "select all" in low
        or ("default" in low and "countr" in low)
    ):
        return (
            "Country DefaultValue uses prm_Country dataset (all values selected).",
            ["default_all_countries"],
        )
    if category == "documentation":
        if "country" in low:
            return (
                "DocumentationPage: branch country (not member home); all countries default.",
                ["doc_country_filter"],
            )
        return (
            "Documentation page updated for this change (client language, filter/column explained).",
            ["doc_page_updated"],
        )
    if "join type" in low or "jointype" in low.replace(" ", ""):
        return (
            "Join Type parameter ValidValues match ticket (e.g. exclude Continuing on New Members Details).",
            ["join_type_filter"],
        )
    if "end date" in low and "start date" in low:
        return ("Date guard when EndDate < StartDate (dashboard parity).", ["date_guard_sql"])
    if "paginated only" in low or "no dashboard" in low:
        return ("git diff must not include .Report/report.json unless ticket names dashboard.", [])
    if "dashboard" in low and "parity" in low:
        return ("Confirm dashboard slicers match paginated parameters in branch diff.", [])
    return (f"Read branch diff + artifact: {text[:100]}", [])


def extract_bullets(summary: str, description: str, comments_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(source: str, block: str) -> None:
        for m in _BULLET.finditer(block):
            t = m.group(1).strip()
            if len(t) < 4:
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append((source, t))
        for section_match in _SCOPE_SECTION.finditer(block):
            pass  # bullets already captured from full block via finditer on paragraphs

    for source, text in (
        ("jira_summary", summary),
        ("jira_description", description),
    ):
        if not text:
            continue
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            if _SCOPE_SECTION.match(lines[i].strip()):
                sec = lines[i].strip()
                i += 1
                chunk: list[str] = []
                while i < len(lines) and not _SCOPE_SECTION.match(lines[i].strip()):
                    chunk.append(lines[i])
                    i += 1
                add(f"jira_description:{sec}", "\n".join(chunk))
            else:
                i += 1
        add(source, text)

    if comments_text:
        for idx, part in enumerate(re.split(r"\[Comment by ", comments_text)):
            body = part.split("]\n", 1)[-1] if "]\n" in part else part
            add(f"jira_comment_{idx}", body)

    return items


def infer_artifact_glob_from_summary(summary: str, description: str = "") -> str | None:
    """Derive deliverable .rdl glob from Jira title (e.g. New Members - Details (paginated))."""
    text = f"{summary}\n{description or ''}"
    match = re.search(r"[-–]\s*(.+?)\s*\(paginated\)", text, re.I)
    if match:
        name = match.group(1).strip()
        if name and len(name) < 120:
            return f"**/{name}.rdl"
    match2 = re.search(
        r"(?:paginated\s+report\s+)?['\"]?([^'\"\n]+?)['\"]?\s*(?:paginated\s+report)?",
        text,
        re.I,
    )
    if match2 and ".rdl" in text.lower():
        name = match2.group(1).strip()
        if name.endswith(".rdl"):
            return f"**/{name}"
        if 3 < len(name) < 80:
            return f"**/{name}.rdl"
    return None


def build_requirement_matrix(
    *,
    ticket_key: str,
    summary: str = "",
    description: str = "",
    comments_text: str = "",
) -> list[MatrixRequirement]:
    bullets = extract_bullets(summary, description, comments_text)
    matrix: list[MatrixRequirement] = []
    n = 0
    for source, text in bullets:
        n += 1
        cat = _classify(text)
        in_scope = cat != "scope" and not _OUT_OF_SCOPE.search(text)
        hint, check_ids = _checks_for_text(text, cat)
        matrix.append(
            MatrixRequirement(
                req_id=f"{ticket_key}-REQ-{n:02d}",
                text=text,
                source=source,
                category=cat,
                in_scope=in_scope,
                verify_hint=hint,
                automated_check_ids=check_ids,
            )
        )
    if not matrix and summary:
        hint, check_ids = _checks_for_text(summary, _classify(summary))
        matrix.append(
            MatrixRequirement(
                req_id=f"{ticket_key}-REQ-01",
                text=summary.strip(),
                source="jira_summary",
                category=_classify(summary),
                in_scope=True,
                verify_hint=hint,
                automated_check_ids=check_ids,
            )
        )
    return matrix


def matrix_to_ticket_profile(
    ticket_key: str,
    summary: str,
    matrix: list[MatrixRequirement],
    *,
    artifact_glob: str = "**/*.rdl",
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    out_scope: list[str] = []
    for row in matrix:
        if not row.in_scope:
            out_scope.append(row.text)
            continue
        if row.automated_check_ids:
            for cid in row.automated_check_ids:
                requirements.append(
                    {
                        "id": cid,
                        "text": row.text,
                        "must_have": True,
                        "req_ref": row.req_id,
                    }
                )
        else:
            requirements.append(
                {
                    "id": f"manual_{row.req_id}",
                    "text": row.text,
                    "must_have": True,
                    "req_ref": row.req_id,
                }
            )
    deduped: dict[str, dict[str, Any]] = {}
    for r in requirements:
        rid = r["id"]
        if rid not in deduped:
            deduped[rid] = r
    return {
        "key": ticket_key,
        "summary": summary,
        "artifact_glob": artifact_glob,
        "scope": {
            "deliverable": summary,
            "in_scope": [artifact_glob],
            "in_scope_requirements": [r.text for r in matrix if r.in_scope],
            "out_of_scope": out_scope,
        },
        "requirements": list(deduped.values()),
        "requirement_matrix": [r.as_dict() for r in matrix],
    }


def format_matrix_markdown(ticket_key: str, summary: str, matrix: list[MatrixRequirement]) -> str:
    lines = [
        f"# Scope matrix — {ticket_key}",
        "",
        f"**Summary:** {summary}",
        "",
        "| ID | In scope | Category | Source | Requirement | How to verify |",
        "|----|----------|----------|--------|-------------|---------------|",
    ]
    for r in matrix:
        scope = "yes" if r.in_scope else "no"
        text = r.text.replace("|", "/")
        hint = r.verify_hint.replace("|", "/")
        lines.append(
            f"| {r.req_id} | {scope} | {r.category} | {r.source} | {text} | {hint} |"
        )
    lines.extend(
        [
            "",
            "**Agent rule:** Do not mark any row `met` until the verify column is satisfied with a file path or grep evidence.",
        ]
    )
    return "\n".join(lines)


def load_jira_from_paginate(ticket_key: str) -> dict[str, Any]:
    """Optional live Jira via Paginate product (same credentials as Paginate MCP)."""
    import os
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "paginate-platform" / "workspace" / "product"
    if not root.is_dir():
        root = Path(os.environ.get("PAGINATE_PRODUCT_ROOT", ""))
    if not root.is_dir():
        return {"ok": False, "error": "paginate product root not found"}
    platform_root = str(root.parent.parent)
    for entry in (platform_root, str(root)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from paginate.jira_intake import fetch_jira_ticket

    return fetch_jira_ticket(ticket_key)
