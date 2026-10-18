"""RDL evidence helpers — Semantic Scout (no external products)."""
from __future__ import annotations

import re


def main_tablix_block(text: str) -> str:
    match = re.search(r'(<Tablix Name="Tablix1"[\s\S]*?</Tablix>)', text)
    return match.group(1) if match else ""


def first_tablix_header_labels(rdl_text: str) -> list[str]:
    labels: list[str] = []
    block = main_tablix_block(rdl_text) or rdl_text
    for m in re.finditer(
        r'<Textbox Name="([^"]*Header)"[^>]*>[\s\S]*?<Value>([^<]*)</Value>',
        block,
        flags=re.DOTALL,
    ):
        labels.append(m.group(2).strip())
    if labels:
        return labels
    rows = re.search(r"<TablixBody>[\s\S]*?<TablixRows>([\s\S]*?)</TablixRows>", block)
    if not rows:
        return []
    first_row = re.search(r"<TablixRow>([\s\S]*?)</TablixRow>", rows.group(1))
    if not first_row:
        return []
    for vm in re.finditer(r"<Value>([^<]+)</Value>", first_row.group(1)):
        val = vm.group(1).strip()
        if val and not val.startswith("="):
            labels.append(val)
    return labels


def first_tablix_detail_fields(rdl_text: str) -> list[str]:
    """First data row Fields! column order in Tablix1."""
    block = main_tablix_block(rdl_text) or rdl_text
    body = re.search(r"<TablixBody>[\s\S]*?</TablixBody>", block)
    if not body:
        return []
    rows = re.findall(r"<TablixRow>([\s\S]*?)</TablixRow>", body.group(0))
    for row in rows:
        fields = re.findall(r"<Value>=Fields!(\w+)\.Value</Value>", row, re.I)
        if fields:
            return [f.lower() for f in fields]
    return []


def country_column_first_ok(rdl_text: str) -> bool:
    headers = first_tablix_header_labels(rdl_text)
    if headers and headers[0].lower().strip() == "country":
        return True
    fields = first_tablix_detail_fields(rdl_text)
    if fields and fields[0] == "country":
        return True
    block = main_tablix_block(rdl_text) or rdl_text
    if re.search(
        r"<Value>Country</Value>[\s\S]{0,2000}<Value>=Fields!country\.Value</Value>",
        block,
        re.I,
    ):
        return True
    return False


def country_filter_in_sql(sql: str) -> bool:
    pattern = re.compile(
        r"coalesce\s*\(\s*(?:[a-z_][\w]*\.)?country\s*,\s*n?'\(blank\)'\s*\)\s+in\s*\(\s*@country\s*\)"
        r"|(?:[a-z_][\w]*\.)?country\s+in\s*\(\s*@country\s*\)",
        re.I,
    )
    return bool(pattern.search(sql or ""))
