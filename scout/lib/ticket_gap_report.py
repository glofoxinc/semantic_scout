"""Per-ticket Jira AC + engineering gap report with ratings (Semantic Scout)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

RequirementStatus = Literal["met", "partial", "missing", "unverified"]
GapKind = Literal["jira_ac", "engineering", "standards", "quality", "process", "bot"]

@dataclass
class Gap:
    kind: GapKind
    issue: str
    detail: str
    severity: Literal["blocker", "gap", "info"] = "gap"
    fix_hint: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "issue": self.issue,
            "detail": self.detail,
            "fix_hint": self.fix_hint,
        }


@dataclass
class RequirementResult:
    req_id: str
    text: str
    status: RequirementStatus
    evidence: str
    must_have: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.req_id,
            "text": self.text,
            "status": self.status,
            "evidence": self.evidence,
            "must_have": self.must_have,
        }


@dataclass
class TicketReport:
    key: str
    summary: str
    artifact_path: str
    jira_rating: int
    delivery_rating: int
    standards_rating: int
    branch_rating: int
    combined_rating: int
    ready_for_pr: bool
    verdict: Literal["CLEAR", "CAUTION", "FIX_FIRST"]
    requirements: list[RequirementResult] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    scope_contract: dict[str, Any] = field(default_factory=dict)

    def delivery_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if g.kind in ("jira_ac", "engineering", "process", "bot")]

    def standards_gaps(self) -> list[Gap]:
        return [g for g in self.gaps if g.kind in ("standards", "quality")]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "summary": self.summary,
            "artifact_path": self.artifact_path,
            "jira_rating": self.jira_rating,
            "delivery_rating": self.delivery_rating,
            "standards_rating": self.standards_rating,
            "branch_rating": self.branch_rating,
            "combined_rating": self.combined_rating,
            "ready_for_pr": self.ready_for_pr,
            "verdict": self.verdict,
            "requirements": [r.as_dict() for r in self.requirements],
            "gaps": [g.as_dict() for g in self.gaps],
            "delivery_gaps": [g.as_dict() for g in self.delivery_gaps()],
            "standards_gaps": [g.as_dict() for g in self.standards_gaps()],
            "scope_contract": self.scope_contract,
        }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _find_artifact(repo_root: Path, glob_pattern: str) -> Path | None:
    hits = _find_artifacts(repo_root, {"artifact_glob": glob_pattern})
    return hits[0] if hits else None


def _find_artifacts(repo_root: Path, profile: dict[str, Any]) -> list[Path]:
    """Every report named on the ticket. AN-5608 is two RDLs, not the first match."""
    patterns = list(profile.get("artifact_globs") or [])
    single = profile.get("artifact_glob")
    if single and single not in patterns:
        patterns.append(single)
    if not patterns:
        return []
    found: list[Path] = []
    for pattern in patterns:
        hits = sorted(repo_root.glob(pattern))
        if not hits:
            hits = sorted(repo_root.rglob(Path(pattern).name))
        for hit in hits:
            if hit.is_file() and hit not in found:
                found.append(hit)

    def _rank(path: Path) -> tuple[int, str]:
        text = str(path).replace("\\", "/").lower()
        score = 0
        if ".paginatedreport/" in text:
            score += 20
        if "/test/" in text or "\\test\\" in text:
            score -= 15
        if re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", text):
            score -= 25
        return (-score, text)

    found.sort(key=_rank)
    return found


def _count_regex(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.I))


def _main_tablix_block(text: str) -> str:
    """Main data grid (Tablix1) — same scope as Paginate gap_checks."""
    match = re.search(r'(<Tablix Name="Tablix1"[\s\S]*?</Tablix>)', text)
    return match.group(1) if match else ""


def _tablix_column_count(text: str) -> int:
    block = _main_tablix_block(text)
    if not block:
        return _count_regex(text, r"<TablixColumn>")
    body = re.search(r"<TablixBody>[\s\S]*?</TablixBody>", block)
    if not body:
        return 0
    return len(re.findall(r"<TablixColumn>", body.group(0)))


def _tablix_column_hierarchy_member_count(text: str) -> int:
    block = _main_tablix_block(text) or text
    hier = re.search(
        r"<TablixColumnHierarchy>[\s\S]*?<TablixMembers>([\s\S]*?)</TablixMembers>",
        block,
    )
    if not hier:
        return 0
    return len(re.findall(r"<TablixMember", hier.group(1)))


def _first_tablix_header_labels(rdl_text: str) -> list[str]:
    """First header row text values in first Tablix (heuristic)."""
    labels: list[str] = []
    for m in re.finditer(
        r'<Textbox Name="([^"]*Header)"[^>]*>.*?<Value>([^<]*)</Value>',
        rdl_text,
        flags=re.DOTALL,
    ):
        labels.append(m.group(2).strip())
    if labels:
        return labels
    block = re.search(r"<TablixRows>.*?<TablixRow>", rdl_text, re.DOTALL)
    if not block:
        return []
    for vm in re.finditer(r"<Value>([^<]+)</Value>", block.group(0)):
        val = vm.group(1).strip()
        if val and not val.startswith("="):
            labels.append(val)
    return labels


def _req_ids_set(req_ids: set[str] | None) -> set[str]:
    return req_ids if req_ids is not None else set()


def _wants_country_checks(req_ids: set[str]) -> bool:
    return bool(
        req_ids
        & {
            "country_filter",
            "country_column_first",
            "default_all_countries",
            "doc_country_filter",
        }
    )


def _wants_doc_checks(req_ids: set[str], requirement_texts: list[str]) -> bool:
    if any(rid.startswith("doc_") or rid == "documentation_clear" for rid in req_ids):
        return True
    return any("document" in t.lower() for t in requirement_texts)


def _wants_filter_on_table_checks(req_ids: set[str], requirement_texts: list[str]) -> bool:
    if not req_ids:
        return False
    if req_ids & {"payment_method_param", "charge_type_param"}:
        return True
    return any(
        "column" in t.lower() and "filter" in t.lower()
        for t in requirement_texts
    )


def _country_doc_explained(text: str) -> bool:
    values = _documentation_values(text)
    if not values:
        return False
    doc_lower = " ".join(values).lower()
    if "country:" not in doc_lower:
        return False
    for label, definition in _glossary_pairs(values):
        if "country" in label.lower():
            return _country_sentence_is_specific(definition)
    return False


def analyze_rdl_engineering(
    rdl_path: Path,
    *,
    req_ids: set[str] | None = None,
    requirement_texts: list[str] | None = None,
) -> tuple[dict[str, bool], list[Gap]]:
    """Evidence-based RDL checks scoped to this ticket's requirement ids (no external MCP)."""
    text = _read_text(rdl_path)
    gaps: list[Gap] = []
    checks: dict[str, bool] = {}
    ids = _req_ids_set(req_ids)
    texts = requirement_texts or []
    country_ticket = _wants_country_checks(ids)
    doc_ticket = _wants_doc_checks(ids, texts)
    filter_table_ticket = _wants_filter_on_table_checks(ids, texts)

    checks["has_country_param"] = bool(
        re.search(r'<ReportParameter Name="Country"', text)
        and re.search(r"<MultiValue>true</MultiValue>", text)
    )
    checks["prm_country_dataset"] = 'DataSet Name="prm_Country"' in text
    checks["null_country_sentinel"] = "COALESCE(country, N'(blank)')" in text
    checks["mainquery_country_filter"] = "@Country" in text and "IN (@Country)" in text
    checks["default_all_from_dataset"] = bool(
        re.search(
            r'<ReportParameter Name="Country"[\s\S]*?<DefaultValue>[\s\S]*?prm_Country',
            text,
        )
    )

    col_count = _tablix_column_count(text)
    member_count = _tablix_column_hierarchy_member_count(text)
    checks["tablix_hierarchy_balanced"] = col_count > 0 and col_count == member_count

    from lib.rdl_checks import country_column_first_ok, country_filter_in_sql

    checks["country_column_first"] = country_column_first_ok(text)

    checks["date_guard"] = "@StartDate" in text and "@EndDate" in text and (
        "@StartDate <= @EndDate" in text or "StartDate.Value" in text
    )
    checks["error_banner"] = "ErrorBanner" in text or "Invalid date range" in text
    checks["no_rows_message"] = "NoRowsMessage" in text

    cascade_ok = False
    for param in ("Branches", "Clubs"):
        if f'ReportParameter Name="{param}"' not in text:
            continue
        for ds_name in re.findall(
            rf'<ReportParameter Name="{param}"[\s\S]*?<DataSetName>([^<]+)</DataSetName>',
            text,
        ):
            ds_block = re.search(
                rf'<DataSet Name="{re.escape(ds_name)}"[\s\S]*?</DataSet>',
                text,
                re.I,
            )
            if ds_block and country_filter_in_sql(ds_block.group(0)):
                cascade_ok = True
                break
        if cascade_ok:
            break
    checks["branch_picker_cascades_country"] = cascade_ok

    doc_gaps = _documentation_client_gaps(text, rdl_path.name) if doc_ticket else []
    filter_gaps = (
        _filter_field_table_gaps(text, rdl_path.name) if filter_table_ticket else []
    )
    checks["documentation_clear"] = (not doc_ticket) or len(doc_gaps) == 0
    checks["doc_country_explained"] = (not doc_ticket) or _country_doc_explained(text)
    checks["filter_fields_on_table"] = (not filter_table_ticket) or len(filter_gaps) == 0
    checks["membership_column"] = "Currently has a membership" in text
    checks["membership_default_no"] = bool(
        re.search(
            r'<ReportParameter Name="CurrentlyHasAMembership"[\s\S]*?<Value>No</Value>',
            text,
        )
    )
    checks["payment_method_param"] = 'ReportParameter Name="PaymentMethod"' in text
    checks["charge_type_param"] = 'ReportParameter Name="ChargeType"' in text
    gaps.extend(doc_gaps)
    gaps.extend(filter_gaps)

    has_country = country_ticket and 'ReportParameter Name="Country"' in text
    if (
        country_ticket
        and "country_column_first" in ids
        and has_country
        and not checks["null_country_sentinel"]
    ):
        gaps.append(
            Gap(
                kind="engineering",
                severity="info",
                issue="NULL country branches can be excluded from results",
                detail=(
                    "Branches with country IS NULL never appear in prm_Country and can be "
                    "dropped when filtering with country IN (@Country) without a (blank) sentinel."
                ),
                fix_hint="Use COALESCE(country, N'(blank)') in prm_Country and the branches CTE.",
            )
        )
    if not checks["tablix_hierarchy_balanced"]:
        gaps.append(
            Gap(
                kind="engineering",
                severity="blocker",
                issue="Tablix column count does not match TablixColumnHierarchy members",
                detail=(
                    f"Tablix1 has {col_count} TablixColumn widths but {member_count} "
                    "TablixColumnHierarchy members. Fabric import often fails with "
                    "PaginatedReportAuthoringError / imports BadRequest."
                ),
                fix_hint=(
                    "When adding a column, add exactly one <TablixMember /> in "
                    "TablixColumnHierarchy (not an extra duplicate). Match Paginate "
                    "check_tablix_column_hierarchy_parity."
                ),
            )
        )
    if has_country and not checks["branch_picker_cascades_country"]:
        gaps.append(
            Gap(
                kind="engineering",
                severity="info",
                issue="Branch Name picker is not filtered by selected Country",
                detail=(
                    "prm_RlsClubsSelection / Clubs dataset does not reference @Country; "
                    "users may still see all RLS branches while MainQuery filters by country."
                ),
                fix_hint="Only if product expects cascade: add @Country to branch list SQL.",
            )
        )

    return checks, gaps


_DOC_PROMPTS_COVERED = frozenset({
    "from",
    "to",
    "branch",
    "branches",
    "location",
    "branch name",
    "start date",
    "end date",
})


def _documentation_page_block(text: str) -> str:
    start = text.find('<Rectangle Name="DocumentationPage">')
    if start < 0:
        match = re.search(r'<Textbox Name="FinalDocumentationBody"[\s\S]*?</Textbox>', text)
        return match.group(0) if match else ""
    depth = 0
    index = start
    while index < len(text):
        opened = text.find("<Rectangle", index)
        closed = text.find("</Rectangle>", index)
        if closed < 0:
            return text[start:]
        if opened != -1 and opened < closed:
            depth += 1
            index = opened + len("<Rectangle")
            continue
        depth -= 1
        index = closed + len("</Rectangle>")
        if depth == 0:
            return text[start:index]
    return text[start:]


def _documentation_values(text: str) -> list[str]:
    block = _documentation_page_block(text)
    return [v.strip() for v in re.findall(r"<Value>([^<]*)</Value>", block) if v.strip()]


def _glossary_pairs(values: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    index = 0
    while index < len(values):
        label = values[index]
        nxt = values[index + 1] if index + 1 < len(values) else ""
        if label.endswith(":") and nxt and not nxt.endswith(":"):
            pairs.append((label[:-1].strip(), nxt))
            index += 2
        else:
            index += 1
    return pairs


def _visible_prompts(text: str) -> list[str]:
    prompts: list[str] = []
    for match in re.finditer(r'<ReportParameter Name="(\w+)"[\s\S]*?</ReportParameter>', text):
        block = match.group(0)
        if re.search(r"<Hidden>\s*true\s*</Hidden>", block, re.I):
            continue
        prompt_m = re.search(r"<Prompt>([^<]*)</Prompt>", block)
        prompts.append((prompt_m.group(1).strip() if prompt_m else match.group(1)))
    return prompts


def _country_sentence_is_specific(definition: str) -> bool:
    low = definition.lower()
    explicit_member = any(
        phrase in low
        for phrase in ("member's home branch", "member's country", "country the member")
    )
    explicit_branch = ("branch" in low) and any(
        phrase in low
        for phrase in (
            "not the member",
            "not where the member",
            "member lives",
            "where the branch is located",
            "branch is located",
            "branch's country",
            "country of the branch",
        )
    )
    return explicit_member or explicit_branch


_SCOPE_FILTER_PARAMS = frozenset({
    "startdate",
    "enddate",
    "branches",
    "clubs",
    "branch",
    "location",
    "userid",
    "userclublist",
    "schedulingcycle",
    "source",
    "jointype",
    "join_type",
    "country",
})
_SQL_WORDS = frozenset({
    "coalesce", "nullif", "ltrim", "rtrim", "and", "or", "where", "case",
    "when", "then", "else", "end", "not", "select", "from", "in", "as",
    "distinct", "top", "on", "join", "inner", "left", "right", "outer",
})


def _outer_select_list(sql: str) -> str:
    text = re.sub(r"\s+", " ", sql.replace("&gt;", ">").replace("&lt;", "<")).strip()
    lower = text.lower()
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            index += 1
            continue
        at_select = (
            depth == 0
            and lower.startswith("select", index)
            and (index == 0 or not text[index - 1].isalnum())
        )
        if not at_select:
            index += 1
            continue
        inner = 0
        cursor = index + 6
        while cursor < len(text):
            if text[cursor] == "(":
                inner += 1
            elif text[cursor] == ")":
                inner -= 1
            elif inner == 0 and lower.startswith("from", cursor) and not text[cursor - 1].isalnum():
                return text[index + 6 : cursor]
            cursor += 1
        return text[index + 6 :]
    return ""


def _split_select_items(select_list: str) -> list[str]:
    items: list[str] = []
    buffer: list[str] = []
    depth = 0
    for char in select_list:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            item = "".join(buffer).strip()
            if item:
                items.append(item)
            buffer = []
        else:
            buffer.append(char)
    tail = "".join(buffer).strip()
    if tail:
        items.append(tail)
    return items


def _output_name(item: str) -> str:
    item = re.sub(r"--.*$", "", item).strip()
    match = re.search(r"\bas\s+([A-Za-z_][\w]*)\s*$", item, re.I)
    if match:
        return match.group(1)
    idents = re.findall(r"[A-Za-z_][\w]*", item)
    return idents[-1] if idents else ""


def _filter_field_table_gaps(text: str, report_name: str = "") -> list[Gap]:
    """A value filter is unfinished until its own field is on the table."""
    match = re.search(
        r'<DataSet Name="MainQuery"[\s\S]*?<CommandText>([\s\S]*?)</CommandText>',
        text,
    )
    if not match:
        return []
    sql = match.group(1)
    flat = re.sub(r"\s+", " ", sql.replace("&gt;", ">").replace("&lt;", "<"))
    flat = re.sub(r"'[^']*'", " ", flat)
    items = _split_select_items(_outer_select_list(sql))
    shown = {name.lower() for name in re.findall(r"Fields!(\w+)\.Value", text)}
    prefix = f"{report_name} — " if report_name else ""
    gaps: list[Gap] = []
    seen: set[str] = set()
    for pred in re.finditer(r"\bIN\s*\(\s*@(\w+)\s*\)", flat, re.I):
        param = pred.group(1)
        if param.lower() in _SCOPE_FILTER_PARAMS:
            continue
        before = flat[max(0, pred.start() - 220) : pred.start()]
        column = ""
        for token in reversed(re.findall(r"[A-Za-z_][\w]*", before)):
            if token.lower() in _SQL_WORDS or token.lower() == param.lower():
                continue
            column = token
            break
        if not column or column.lower() in seen:
            continue
        seen.add(column.lower())
        aliases = [
            _output_name(item)
            for item in items
            if re.search(rf"\b{re.escape(column)}\b", item, re.I)
        ]
        if any(alias.lower() in shown for alias in aliases if alias):
            continue
        gaps.append(
            Gap(
                kind="engineering",
                severity="gap",
                issue=f"{prefix}{param} filter is not on the table",
                detail=(
                    f"The query limits rows by {column}. That field is not a tablix column. "
                    "A similarly named column that uses a different field does not count."
                ),
                fix_hint=(
                    f"Add {column} to the outer SELECT and as its own column, "
                    "named the way the filter is named. Keep a different existing column."
                ),
            )
        )
    return gaps


def _documentation_client_gaps(text: str, report_name: str = "") -> list[Gap]:
    """Documentation page must explain each new filter in client language.

    These are delivery gaps. A query change without the sentence is not done.
    """
    values = _documentation_values(text)
    if not values:
        return []
    doc_lower = " ".join(values).lower()
    gaps: list[Gap] = []
    prefix = f"{report_name} — " if report_name else ""
    for prompt in _visible_prompts(text):
        low = prompt.lower()
        if not low or low in _DOC_PROMPTS_COVERED or low.endswith(" from") or low.endswith(" to"):
            continue
        if f"{low}:" in doc_lower:
            continue
        whose = ""
        if low == "country":
            whose = (
                " Say it is the branch's country, not the country the member lives in,"
                " and that all countries start selected."
            )
        gaps.append(
            Gap(
                kind="engineering",
                severity="gap",
                issue=f"{prefix}Documentation page does not explain the '{prompt}' filter",
                detail=f"The parameter exists. The documentation page has no '{prompt}:' sentence.{whose}",
                fix_hint="Add a client sentence for what the filter limits and what is selected by default.",
            )
        )
    for label, definition in _glossary_pairs(values):
        low_def = definition.lower().strip()
        if "country" in label.lower() and not _country_sentence_is_specific(definition):
            gaps.append(
                Gap(
                    kind="engineering",
                    severity="gap",
                    issue=f"{prefix}'{label}' does not say whose country it is",
                    detail=definition.strip(),
                    fix_hint=(
                        "Say the branch's country, not the country the member lives in, "
                        "or the member's home branch when that is the real meaning."
                    ),
                )
            )
        if "whether the member still has a membership" in low_def and "ended" not in low_def:
            gaps.append(
                Gap(
                    kind="engineering",
                    severity="gap",
                    issue=f"{prefix}'{label}' does not say this is a membership after the one in the row ended",
                    detail=definition.strip(),
                    fix_hint="Say whether the person still has a membership after this one ended.",
                )
            )
        if "the filter starts on" in low_def:
            gaps.append(
                Gap(
                    kind="engineering",
                    severity="gap",
                    issue=f"{prefix}'{label}' describes the control instead of what the reader will see",
                    detail=definition.strip(),
                    fix_hint="Say the list opens on people who do not still have a membership.",
                )
            )
        if low_def.strip(" .") in {"the payment method used", "the payment method used for the transaction"}:
            gaps.append(
                Gap(
                    kind="engineering",
                    severity="gap",
                    issue=f"{prefix}'{label}' does not say how the sale was paid",
                    detail=definition.strip(),
                    fix_hint="Say how the sale was paid, such as card, direct debit, or cash.",
                )
            )
    if "payment_method_type" in text.lower() and "payment_type_formatted" in text.lower():
        if "formatted payment type" not in doc_lower:
            gaps.append(
                Gap(
                    kind="engineering",
                    severity="gap",
                    issue=f"{prefix}Payment Method filter and Payment Type column are not the same field",
                    detail=(
                        "The filter uses payment method type. The column uses the formatted payment type. "
                        "The documentation page does not say they can differ."
                    ),
                    fix_hint="Say the Payment Type column can show a formatted payment type, which is not always this filter.",
                )
            )
    return gaps


def _dedupe_gaps(gaps: list[Gap]) -> list[Gap]:
    seen: set[tuple[str, str]] = set()
    out: list[Gap] = []
    for g in gaps:
        key = (g.kind, g.issue)
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    return out


def _req_status_from_checks(req_id: str, checks: dict[str, bool]) -> tuple[RequirementStatus, str]:
    if req_id.startswith("manual_"):
        return (
            "unverified",
            "Manual matrix row — open artifact and confirm in Scout card with path evidence.",
        )
    mapping = {
        "country_filter": (
            "has_country_param",
            "prm_country_dataset",
            "mainquery_country_filter",
        ),
        "country_column_first": ("country_column_first",),
        "default_all_countries": ("default_all_from_dataset",),
        "doc_country_filter": ("doc_country_explained",),
        "documentation_clear": ("documentation_clear",),
        "membership_column": ("membership_column",),
        "membership_default_no": ("membership_default_no",),
        "payment_method_param": ("payment_method_param",),
        "charge_type_param": ("charge_type_param",),
    }
    keys = mapping.get(req_id, ())
    if not keys:
        return "unverified", f"No automated RDL check for requirement id '{req_id}' — verify via matrix hint."
    missing = [k for k in keys if not checks.get(k)]
    if not missing:
        return "met", f"RDL checks passed: {', '.join(keys)}"
    if len(missing) < len(keys):
        return "partial", f"Partial: failed {', '.join(missing)}"
    return "missing", f"Failed checks: {', '.join(missing)}"


def _score_requirements(results: list[RequirementResult]) -> int:
    if not results:
        return 0
    total = 0.0
    for r in results:
        if r.status == "met":
            total += 100
        elif r.status == "partial":
            total += 50
        elif r.status == "unverified":
            total += 0
    score = int(round(total / len(results)))
    if any(r.must_have and r.status == "missing" for r in results):
        return min(score, 49)
    if any(r.must_have and r.status == "unverified" for r in results):
        return min(score, 59)
    return score


def _score_delivery_gaps(gaps: list[Gap]) -> int:
    """Ticket delivery only — engineering/jira/process blockers, not catalogue debt."""
    score = 100
    for g in gaps:
        if g.kind not in ("jira_ac", "engineering", "process", "bot"):
            continue
        if g.severity == "blocker":
            score -= 30
        elif g.severity == "gap":
            score -= 12
        elif g.severity == "info":
            score -= 3
    return max(0, min(100, score))


def _standards_from_paginate(payload: dict[str, Any] | None) -> int | None:
    """None = standards pass not run (do not treat as 0% failure)."""
    if not payload:
        return None
    gaps = payload.get("gaps") or {}
    if isinstance(gaps, dict) and "score" in gaps:
        return int(gaps.get("score") or 0)
    return 100 if payload.get("ok") else 50


def _score_branch(gaps: list[Gap], artifact_exists: bool) -> int:
    """Legacy combined penalty — prefer delivery_rating + standards_rating."""
    if not artifact_exists:
        return 0
    return _score_delivery_gaps(gaps)


def _is_delivery_gap(g: Gap) -> bool:
    """Ticket delivery only — bot-ahead is separate (see review.bot_resolution)."""
    return g.kind in ("jira_ac", "engineering", "process")


def _ready_for_pr(jira: int, delivery: int, delivery_gaps: list[Gap]) -> bool:
    if any(g.severity == "blocker" for g in delivery_gaps if _is_delivery_gap(g)):
        return False
    if any(g.kind == "engineering" and g.severity == "gap" for g in delivery_gaps):
        return False
    if jira < 90 or delivery < 85:
        return False
    return True


def _verdict(
    jira: int,
    delivery: int,
    delivery_gaps: list[Gap],
) -> Literal["CLEAR", "CAUTION", "FIX_FIRST"]:
    """Verdict uses Jira AC + engineering/process only — never Paginate catalogue debt."""
    if any(g.severity == "blocker" for g in delivery_gaps if _is_delivery_gap(g)):
        return "FIX_FIRST"
    combined = round(0.55 * jira + 0.45 * delivery)
    if combined >= 85 and jira >= 90 and delivery >= 85:
        return "CLEAR"
    if combined >= 70 and jira >= 75:
        return "CAUTION"
    return "FIX_FIRST"


def _paginate_nested_gaps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect gap dicts from analyze_rdl JSON (top-level or nested under gaps)."""
    found: list[dict[str, Any]] = []
    for bf in payload.get("blocking_failures") or []:
        if isinstance(bf, dict):
            found.append(bf)
    block = payload.get("gaps")
    if isinstance(block, dict):
        for item in block.get("gaps") or []:
            if isinstance(item, dict):
                found.append(item)
    elif isinstance(block, list):
        for item in block:
            if isinstance(item, dict):
                found.append(item)
    return found


def _paginate_severity_to_gap(sev: str) -> Literal["blocker", "gap", "info"]:
    if sev == "error":
        return "gap"
    if sev == "warning":
        return "gap"
    return "info"


def merge_paginate_json(
    paginate_payload: dict[str, Any],
    ticket_key: str,
    *,
    ignore_standards_ids: set[str] | None = None,
) -> list[Gap]:
    """Paginate findings are standards/catalogue — they do not reduce delivery_rating."""
    ignore = ignore_standards_ids or set()
    out: list[Gap] = []
    seen_ids: set[str] = set()
    for item in _paginate_nested_gaps(paginate_payload):
        gid = str(item.get("id") or "paginate_gap")
        if gid in ignore or gid in seen_ids:
            continue
        seen_ids.add(gid)
        sev = _paginate_severity_to_gap(str(item.get("severity") or "info"))
        out.append(
            Gap(
                kind="standards",
                severity=sev,
                issue=gid,
                detail=item.get("message") or "",
                fix_hint=item.get("action")
                or "Paginate catalogue/standards — fix if your team gates on MCP 100%.",
            )
        )
    pre = paginate_payload.get("preflight_checklist") or {}
    for item in pre.get("items") or []:
        if item.get("passed") is False and item.get("manual") is not True:
            pid = f"preflight:{item.get('id')}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            out.append(
                Gap(
                    kind="standards",
                    severity="gap",
                    issue=pid,
                    detail=item.get("label") or "",
                )
            )
    if paginate_payload.get("ok") is False and not out:
        out.append(
            Gap(
                kind="standards",
                severity="gap",
                issue="paginate_ok_false",
                detail=f"Paginate full profile did not pass for {ticket_key} (no gap details returned).",
            )
        )
    return out


def merge_process_context(ctx: dict[str, Any]) -> list[Gap]:
    out: list[Gap] = []
    if ctx.get("circuit_reviewed_sha") and ctx.get("head_sha"):
        if ctx["circuit_reviewed_sha"] != ctx["head_sha"]:
            out.append(
                Gap(
                    kind="process",
                    severity="gap",
                    issue="Circuit bot review is stale",
                    detail=(
                        f"Reviewed {ctx['circuit_reviewed_sha'][:8]}; PR head is "
                        f"{ctx['head_sha'][:8]}. Inline threads may not reflect fixes."
                    ),
                    fix_hint="Comment /circuit review on the PR or re-request review.",
                )
            )
    if ctx.get("require_pbrs_signoff") and not ctx.get("pbrs_signed_off"):
        out.append(
            Gap(
                kind="process",
                severity="gap",
                issue="PBRS / Service export not verified in this run",
                detail="PDF/Excel, parameter defaults, and grid layout need manual sign-off.",
                fix_hint="Open the report in the service and confirm the new filters, defaults, and documentation page.",
            )
        )
    for note in ctx.get("bot_findings_resolved") or []:
        out.append(
            Gap(
                kind="bot",
                severity="info",
                issue=f"Historical bot finding (addressed in code check): {note}",
                detail="Re-run Circuit on latest commit to close the thread.",
            )
        )
    return out


def evaluate_ticket_profile(
    profile: dict[str, Any],
    repo_root: Path,
    *,
    bundle: dict[str, Any] | None = None,
    paginate_by_ticket: dict[str, dict[str, Any]] | None = None,
    process_ctx: dict[str, Any] | None = None,
    branch_ctx: dict[str, Any] | None = None,
) -> TicketReport:
    from lib.bot_preflight import run_bot_preflight
    from lib.git_scope import git_changed_files, git_diff_excerpt, scope_violations
    from lib.jira_scope_contract import build_scope_contract
    from lib.requirement_evidence import build_checks_bundle, evaluate_all_requirements

    key = profile["key"]
    summary = profile.get("summary", "")
    artifacts = _find_artifacts(repo_root, profile)
    artifact = artifacts[0] if artifacts else None
    path_str = "; ".join(str(path) for path in artifacts)

    requirements_out: list[RequirementResult] = []
    gaps: list[Gap] = []
    checks: dict[str, bool] = {}
    req_status_map: dict[str, str] = {}

    bctx = branch_ctx or {}
    base_ref = bctx.get("base_ref")
    changed_paths: list[str] = list(bctx.get("changed_paths") or [])
    diff_excerpt = str(bctx.get("diff_excerpt") or "")
    if base_ref and repo_root.is_dir():
        if not changed_paths:
            changed_paths = git_changed_files(repo_root, str(base_ref))
        if not diff_excerpt:
            diff_excerpt = git_diff_excerpt(repo_root, str(base_ref))

    scope = profile.get("scope") or {}
    in_scope: list[str] = list(dict.fromkeys(scope.get("in_scope") or []))
    for g in profile.get("artifact_globs") or []:
        if g not in in_scope:
            in_scope.append(str(g))
    if profile.get("artifact_glob") and profile["artifact_glob"] not in in_scope:
        in_scope.append(str(profile["artifact_glob"]))
    out_scope = list(scope.get("out_of_scope") or [])
    if bundle:
        out_scope.extend(bundle.get("default_out_of_scope") or [])
    scope_mode = str(bctx.get("scope_mode") or "ticket")
    if changed_paths and in_scope:
        for viol in scope_violations(
            changed_paths,
            in_scope=in_scope,
            out_of_scope=out_scope,
            scope_mode=scope_mode,
        ):
            sev = viol["severity"]
            if sev == "info":
                gap_sev: Literal["blocker", "gap", "info"] = "info"
            else:
                gap_sev = "blocker" if sev == "blocker" else "gap"
            gaps.append(
                Gap(
                    kind="process",
                    severity=gap_sev,
                    issue=f"Out-of-scope path on branch: {viol['path']}",
                    detail=viol["reason"],
                    fix_hint="Revert path or get Jira scope amendment before PR.",
                )
            )

    if not artifacts:
        for req in profile.get("requirements") or []:
            req_status_map[req["id"]] = "missing"
            requirements_out.append(
                RequirementResult(
                    req_id=req["id"],
                    text=req["text"],
                    status="missing",
                    evidence=f"Artifact not found for glob {profile.get('artifact_glob')}",
                    must_have=req.get("must_have", True),
                )
            )
            gaps.append(
                Gap(
                    kind="jira_ac",
                    severity="blocker",
                    issue=f"Deliverable file missing for {key}",
                    detail=str(profile.get("artifact_globs") or profile.get("artifact_glob", "")),
                )
            )
    else:
        req_list = profile.get("requirements") or []
        req_id_set = {str(r["id"]) for r in req_list}
        req_texts = [str(r.get("text") or "") for r in req_list]
        checks, eng_gaps = build_checks_bundle(artifacts, req_id_set, req_texts)
        gaps.extend(eng_gaps)
        requirements_out = evaluate_all_requirements(
            req_list,
            artifacts=artifacts,
            checks=checks,
            changed_paths=changed_paths,
            diff_excerpt=diff_excerpt,
        )
        for row in requirements_out:
            req_status_map[row.req_id] = row.status
            if row.status == "missing":
                gaps.append(
                    Gap(
                        kind="jira_ac",
                        severity="blocker",
                        issue=row.text,
                        detail=row.evidence,
                    )
                )
            elif row.status == "partial":
                gaps.append(
                    Gap(
                        kind="jira_ac",
                        severity="gap",
                        issue=row.text,
                        detail=row.evidence,
                    )
                )

    if changed_paths:
        bot_result = run_bot_preflight(changed_paths, diff_excerpt)
        for pred in bot_result.get("predictions") or []:
            score = float(pred.get("score") or 0)
            sev: Literal["blocker", "gap", "info"] = (
                "blocker" if score >= 5.0 else "gap" if score >= 3.5 else "info"
            )
            gaps.append(
                Gap(
                    kind="bot",
                    severity=sev,
                    issue=pred.get("likely_bot_finding") or "Likely bot comment",
                    detail=pred.get("why_it_happens") or "",
                    fix_hint=pred.get("do_before_opening_pr") or "",
                )
            )

    merged_ctx = {**(process_ctx or {}), **{k: v for k, v in bctx.items() if k.startswith("circuit") or k.startswith("pbrs") or k == "head_sha"}}
    if merged_ctx:
        gaps.extend(merge_process_context(merged_ctx))

    gaps = _dedupe_gaps(gaps)

    jira_rating = _score_requirements(requirements_out)
    paginate_payload = (paginate_by_ticket or {}).get(key)
    standards_rating = _standards_from_paginate(paginate_payload)
    delivery_gaps_only = [g for g in gaps if _is_delivery_gap(g)]
    delivery_rating = _score_delivery_gaps(delivery_gaps_only)
    branch_rating = delivery_rating
    if standards_rating is None:
        combined = round(0.5 * jira_rating + 0.5 * delivery_rating)
    else:
        combined = round(
            0.4 * jira_rating + 0.4 * delivery_rating + 0.2 * standards_rating
        )
    verdict = _verdict(jira_rating, delivery_rating, delivery_gaps_only)
    ready = _ready_for_pr(jira_rating, delivery_rating, delivery_gaps_only)

    scope_bundle = bundle or {"bundle_id": "", "default_out_of_scope": []}
    scope_contract = build_scope_contract(
        scope_bundle,
        profile,
        artifact_path=artifact,
        requirement_status=req_status_map,
    )

    std_for_report = standards_rating if standards_rating is not None else -1

    return TicketReport(
        key=key,
        summary=summary,
        artifact_path=path_str,
        jira_rating=jira_rating,
        delivery_rating=delivery_rating,
        standards_rating=std_for_report,
        branch_rating=branch_rating,
        combined_rating=combined,
        ready_for_pr=ready,
        verdict=verdict,
        requirements=requirements_out,
        gaps=gaps,
        scope_contract=scope_contract.as_dict(),
    )


def load_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_bundle_report(
    bundle_path: Path,
    repo_root: Path,
    *,
    paginate_by_ticket: dict[str, dict[str, Any]] | None = None,
    process_ctx: dict[str, Any] | None = None,
    branch_ctx: dict[str, Any] | None = None,
) -> list[TicketReport]:
    bundle = load_bundle(bundle_path)
    reports: list[TicketReport] = []
    for profile in bundle.get("tickets") or []:
        reports.append(
            evaluate_ticket_profile(
                profile,
                repo_root,
                bundle=bundle,
                paginate_by_ticket=paginate_by_ticket,
                process_ctx=process_ctx,
                branch_ctx=branch_ctx,
            )
        )
    return reports


def format_ticket_list(reports: list[TicketReport]) -> str:
    lines: list[str] = [
        "=" * 72,
        "SEMANTIC SCOUT — TICKET GAP REPORT",
        "(Documentation sentences are delivery gaps. A filter in the query is not done until the page explains it.)",
        "=" * 72,
        "",
    ]
    for rep in reports:
        lines.append(f"### {rep.key} — {rep.summary}")
        lines.append(f"Artifact: {rep.artifact_path or '(not found)'}")
        ready = "YES" if rep.ready_for_pr else "NO"
        std_label = (
            "n/a (not run)"
            if rep.standards_rating < 0
            else f"{rep.standards_rating}/100"
        )
        lines.append(
            f"Ratings: Jira {rep.jira_rating}/100 | Delivery (branch) {rep.delivery_rating}/100 | "
            f"Standards {std_label} | Combined {rep.combined_rating}/100"
        )
        lines.append(f"READY (Jira+delivery): {ready} | Verdict: {rep.verdict}")
        lines.append("")
        if rep.scope_contract:
            sc = rep.scope_contract
            lines.append("SCOPE CONTRACT:")
            lines.append(f"  Deliverable: {sc.get('deliverable_one_liner', '')}")
            for item in sc.get("in_scope") or []:
                lines.append(f"  In scope: {item}")
            for item in sc.get("out_of_scope") or []:
                lines.append(f"  Out of scope: {item}")
            for ln in sc.get("lines") or []:
                lines.append(
                    f"  [{ln.get('status')}] ({ln.get('category')}) {ln.get('label')}"
                )
                if ln.get("evidence"):
                    lines.append(f"      {ln.get('evidence')}")
        lines.append("")
        lines.append("Jira requirements:")
        for r in rep.requirements:
            lines.append(f"  [{r.status}] {r.text} — {r.evidence}")
        lines.append("")
        delivery = rep.delivery_gaps()
        standards = rep.standards_gaps()
        if delivery:
            lines.append("Delivery gaps (ticket / engineering / process):")
            for g in delivery:
                prefix = g.severity.upper()
                lines.append(f"  - [{prefix}] ({g.kind}) {g.issue}")
                if g.detail:
                    lines.append(f"      {g.detail}")
                if g.fix_hint:
                    lines.append(f"      Fix: {g.fix_hint}")
        else:
            lines.append("Delivery gaps: NONE")
        lines.append("")
        if standards:
            lines.append("Standards gaps (optional external audit — not used in v5):")
            for g in standards:
                lines.append(f"  - ({g.kind}) {g.issue}")
                if g.detail:
                    lines.append(f"      {g.detail}")
        else:
            lines.append("Standards gaps: NONE")
        lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Semantic Scout gap report from a bundle JSON")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--circuit-reviewed-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    from lib.git_scope import git_changed_files, git_diff_excerpt

    process_ctx = {
        "circuit_reviewed_sha": args.circuit_reviewed_sha or None,
        "head_sha": args.head_sha or None,
    }
    reports = run_bundle_report(
        args.bundle,
        args.repo_root,
        process_ctx=process_ctx,
        branch_ctx={
            "base_ref": args.base_ref,
            "changed_paths": git_changed_files(args.repo_root, args.base_ref),
            "diff_excerpt": git_diff_excerpt(args.repo_root, args.base_ref),
            "scope_mode": "ticket",
        },
    )
    if args.json:
        print(json.dumps([r.as_dict() for r in reports], indent=2))
    else:
        print(format_ticket_list(reports))


if __name__ == "__main__":
    main()
