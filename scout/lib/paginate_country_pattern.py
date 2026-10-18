"""Shared country @Country SQL detection (aligned with Paginate country_delivery)."""
from __future__ import annotations

import re

_COUNTRY_IN_FILTER = re.compile(
    r"coalesce\s*\(\s*(?:[a-z_][\w]*\.)?country\s*,\s*n?'\(blank\)'\s*\)\s+in\s*\(\s*@country\s*\)"
    r"|(?:[a-z_][\w]*\.)?country\s+in\s*\(\s*@country\s*\)",
    re.I,
)


def country_filter_in_sql(sql: str) -> bool:
    return bool(_COUNTRY_IN_FILTER.search(sql or ""))
