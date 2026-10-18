"""Ticket-scoped requirement evaluation — evidence per Jira row (Semantic Scout)."""
from __future__ import annotations

import re
from pathlib import Path

from lib.ticket_gap_report import (
    RequirementResult,
    RequirementStatus,
    _country_doc_explained,
    _documentation_client_gaps,
    _documentation_values,
    _filter_field_table_gaps,
    _first_tablix_header_labels,
    _main_tablix_block,
    _read_text,
    _tablix_column_count,
    _tablix_column_hierarchy_member_count,
    analyze_rdl_engineering,
)

_COUNTRY_IN_SQL = re.compile(
    r"coalesce\s*\(\s*(?:[a-z_][\w]*\.)?country\s*,\s*n?'\(blank\)'\s*\)\s+in\s*\(\s*@country\s*\)"
    r"|(?:[a-z_][\w]*\.)?country\s+in\s*\(\s*@country\s*\)",
    re.I,
)


def _country_filter_in_sql(sql: str) -> bool:
    return bool(_COUNTRY_IN_SQL.search(sql or ""))


def build_checks_bundle(
    artifacts: list[Path],
    req_ids: set[str],
    requirement_texts: list[str],
) -> tuple[dict[str, bool], list]:
    """Merge structural + scoped RDL checks across all ticket artifacts."""
    checks: dict[str, bool] = {}
    all_gaps = []
    for path in artifacts:
        file_checks, eng_gaps = analyze_rdl_engineering(
            path,
            req_ids=req_ids,
            requirement_texts=requirement_texts,
        )
        all_gaps.extend(eng_gaps)
        if not checks:
            checks = dict(file_checks)
        else:
            for name, passed in file_checks.items():
                checks[name] = bool(checks.get(name)) and passed
    return checks, all_gaps


def _diff_touches_artifact(changed_paths: list[str], artifact: Path) -> bool:
    if not changed_paths:
        return False
    name = artifact.name.lower()
    parts = {p.replace("\\", "/").lower() for p in changed_paths}
    return any(name in p or p.endswith(name) for p in parts)


def _requirement_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-z]{4,}", text.lower())
    stop = {
        "add",
        "the",
        "report",
        "paginated",
        "members",
        "details",
        "must",
        "should",
        "with",
        "that",
        "this",
        "from",
        "into",
        "have",
        "been",
        "will",
        "when",
        "where",
        "ticket",
        "jira",
    }
    return [w for w in words if w not in stop][:8]


def evaluate_requirement(
    req: dict,
    *,
    artifacts: list[Path],
    checks: dict[str, bool],
    changed_paths: list[str],
    diff_excerpt: str,
) -> tuple[RequirementStatus, str]:
    """Map one Jira requirement id + text to met | partial | missing | unverified."""
    rid = str(req.get("id") or "")
    text = str(req.get("text") or "")
    low = text.lower()

    if rid.startswith("manual_"):
        return _evaluate_manual(text, artifacts, changed_paths, diff_excerpt)

    automated = {
        "country_filter": (
            ["has_country_param", "prm_country_dataset", "mainquery_country_filter"],
            "Country multi-value parameter, prm_Country dataset, MainQuery IN (@Country)",
        ),
        "country_column_first": (
            ["country_column_first"],
            "First visible grid header is Country",
        ),
        "default_all_countries": (
            ["default_all_from_dataset"],
            "Country default selects all values from prm_Country",
        ),
        "doc_country_filter": (
            ["doc_country_explained"],
            "Documentation explains branch country (not member home) and default all countries",
        ),
        "doc_page_updated": (
            ["documentation_page_present"],
            "Documentation page exists and branch diff touches documentation content",
        ),
        "date_guard_sql": (
            ["date_guard"],
            "Start/end date guard in MainQuery or parameters",
        ),
        "join_type_filter": (
            ["join_type_valid"],
            "Join Type parameter excludes Continuing when ticket requires",
        ),
    }

    if rid in automated:
        keys, label = automated[rid]
        missing = [k for k in keys if not checks.get(k)]
        if not missing:
            paths = ", ".join(p.name for p in artifacts)
            return "met", f"{paths}: {label}"
        if len(missing) < len(keys):
            return "partial", f"Partial {label}; failed: {', '.join(missing)}"
        return "missing", f"Missing {label}; failed: {', '.join(missing)}"

    if rid == "documentation_clear" or (rid.startswith("doc_") and rid not in automated):
        if artifacts and checks.get("documentation_page_present"):
            doc_gaps = []
            for art in artifacts:
                doc_gaps.extend(_documentation_client_gaps(_read_text(art), art.name))
            if not doc_gaps:
                return "met", "Documentation prompts covered on page"
            return "partial", f"Doc gaps: {doc_gaps[0].issue}"
        return "missing", "No documentation page or content found"

    # Keyword fallback tied to ticket text (not global RDL rules)
    if "document" in low and artifacts:
        if checks.get("doc_country_explained") or checks.get("documentation_clear"):
            return (
                "met" if checks.get("doc_country_explained", checks.get("documentation_clear")) else "partial",
                "Documentation check from ticket wording",
            )

    return _evaluate_manual(text, artifacts, changed_paths, diff_excerpt)


def _evaluate_manual(
    text: str,
    artifacts: list[Path],
    changed_paths: list[str],
    diff_excerpt: str,
) -> tuple[RequirementStatus, str]:
    if not artifacts:
        return "missing", "Deliverable file not found on branch"
    keys = _requirement_keywords(text)
    if not keys:
        return "unverified", "Open artifact and confirm against AC (no keywords to scan)"

    touched = [a for a in artifacts if _diff_touches_artifact(changed_paths, a)]
    if not touched and changed_paths:
        return (
            "unverified",
            f"Diff does not include deliverable ({artifacts[0].name}); confirm intentional",
        )

    hay = diff_excerpt.lower()
    for art in artifacts:
        hay += "\n" + _read_text(art).lower()[:120_000]
    hits = sum(1 for k in keys if k in hay)
    if hits >= max(2, len(keys) // 2):
        return "met", f"Evidence keywords in diff/artifact: {', '.join(keys[:5])}"
    if hits >= 1:
        return "partial", f"Weak keyword match ({hits}/{len(keys)}); read file to confirm"
    return "unverified", f"No keyword evidence for: {', '.join(keys)} — read {artifacts[0].name}"


def enrich_checks_for_requirements(
    artifacts: list[Path],
    checks: dict[str, bool],
    req_ids: set[str],
    *,
    changed_paths: list[str] | None = None,
) -> dict[str, bool]:
    """Add checks derived from requirement ids (not global heuristics)."""
    if not artifacts:
        return checks
    text = "\n".join(_read_text(p) for p in artifacts)
    has_doc = "DocumentationPage" in text or "FinalDocumentationBody" in text
    doc_in_diff = False
    if changed_paths and artifacts:
        for art in artifacts:
            if _diff_touches_artifact(changed_paths, art):
                doc_in_diff = True
                break
    checks["documentation_page_present"] = has_doc and (doc_in_diff or not changed_paths)
    if "join_type_valid" in req_ids or any("join" in r for r in req_ids):
        join_block = re.search(
            r'<ReportParameter Name="JoinType"[\s\S]*?</ReportParameter>',
            text,
            re.I,
        )
        if join_block:
            has_continuing = "Continuing" in join_block.group(0)
            checks["join_type_valid"] = not has_continuing or "allow_continuing" in req_ids
        else:
            checks["join_type_valid"] = True
    mq = re.search(
        r'<DataSet Name="MainQuery"[\s\S]*?<CommandText>([\s\S]*?)</CommandText>',
        text,
    )
    if mq and "mainquery_country_filter" not in checks:
        sql = mq.group(1)
        checks["mainquery_country_filter"] = "@Country" in sql and _country_filter_in_sql(sql)
    return checks


def evaluate_all_requirements(
    requirements: list[dict],
    *,
    artifacts: list[Path],
    checks: dict[str, bool],
    changed_paths: list[str],
    diff_excerpt: str,
) -> list[RequirementResult]:
    req_ids = {str(r["id"]) for r in requirements}
    checks = enrich_checks_for_requirements(
        artifacts, checks, req_ids, changed_paths=changed_paths
    )
    out: list[RequirementResult] = []
    for req in requirements:
        status, evidence = evaluate_requirement(
            req,
            artifacts=artifacts,
            checks=checks,
            changed_paths=changed_paths,
            diff_excerpt=diff_excerpt,
        )
        out.append(
            RequirementResult(
                req_id=str(req.get("id")),
                text=str(req.get("text") or ""),
                status=status,
                evidence=evidence,
                must_have=bool(req.get("must_have", True)),
            )
        )
    return out
