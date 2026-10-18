"""Bot comment prediction — Semantic Scout (learned corpus, no Paginate)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.bot_preflight_advisor import format_preflight_block, predict_bot_risks

DATA_INTEL = Path(__file__).resolve().parents[1] / "data" / "bot_learned_intelligence.json"


def run_bot_preflight(
    changed_paths: list[str],
    diff_excerpt: str = "",
    *,
    top_n: int = 10,
    min_score: float = 2.0,
) -> dict[str, Any]:
    intel_path = DATA_INTEL if DATA_INTEL.is_file() else None
    return predict_bot_risks(
        changed_paths,
        diff_excerpt,
        intelligence_path=intel_path,
        top_n=top_n,
        min_score=min_score,
    )


def bot_preflight_to_gaps(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert predictions to gap-shaped dicts for merge into TicketReport."""
    gaps: list[dict[str, Any]] = []
    for p in result.get("predictions") or []:
        score = float(p.get("score") or 0)
        sev = "blocker" if score >= 5.0 else "gap" if score >= 3.5 else "info"
        gaps.append(
            {
                "kind": "bot",
                "severity": sev,
                "issue": p.get("likely_bot_finding") or p.get("pattern_id"),
                "detail": p.get("why_it_happens") or "",
                "fix_hint": p.get("do_before_opening_pr") or "",
                "score": score,
            }
        )
    return gaps


def load_engineering_bot_patterns() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parents[1] / "data" / "bot_intelligence.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return list(raw.get("patterns") or [])


def scan_engineering_patterns(
    rdl_text: str,
    report_name: str = "",
) -> list[dict[str, Any]]:
    """Static engineering patterns (NULL country, tablix, etc.) from bot_intelligence.json."""
    hits: list[dict[str, Any]] = []
    low = rdl_text.lower()
    for p in load_engineering_bot_patterns():
        det = (p.get("detection") or "").lower()
        if not det:
            continue
        matched = False
        if "coalesce" in det and "country" in det and "in (@country)" in low:
            if "coalesce(country" not in low.replace(" ", "") and "country in (@country)" in low:
                matched = True
        if "tablixcolumn" in det.replace(" ", "") and "tablixmember" in det.replace(" ", ""):
            pass  # handled by structural tablix check
        if p.get("id") == "null_country_branches":
            normalized = low.replace(" ", "")
            if "in(@country)" in normalized and "coalesce(country" not in normalized:
                matched = True
        if matched:
            hits.append(
                {
                    "kind": "engineering",
                    "severity": p.get("severity", "gap"),
                    "issue": p.get("title") or p.get("id"),
                    "detail": p.get("detection") or "",
                    "fix_hint": p.get("fix_hint") or "",
                }
            )
    prefix = f"{report_name} — " if report_name else ""
    for h in hits:
        h["issue"] = f"{prefix}{h['issue']}"
    return hits
