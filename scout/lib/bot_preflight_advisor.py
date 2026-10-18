"""Proactive bot-comment prediction from learned corpus + local diff paths."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_INTEL = Path(__file__).resolve().parents[1] / "data" / "bot_learned_intelligence.json"
CORPUS_INTEL = (
    Path(__file__).resolve().parents[2]
    / "corpus"
    / "intelligence"
    / "learned_bot_intelligence.json"
)


def _load_intelligence(path: Path | None = None) -> dict:
    for candidate in (path, DEFAULT_INTEL, CORPUS_INTEL):
        if candidate is not None and candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {"patterns": []}


def _path_blob(paths: list[str]) -> str:
    return "\n".join(p.replace("\\", "/").lower() for p in paths)


def _score_pattern(pattern: dict, path_blob: str, diff_excerpt: str) -> float:
    score = 0.0
    hints = pattern.get("match_hints") or []
    for h in hints:
        if h.lower() in path_blob or h.lower() in diff_excerpt.lower():
            score += 2.0
    for ps in pattern.get("path_signals") or []:
        if ps.lower() in path_blob:
            score += 2.5
    tags = pattern.get("artifact_tags") or {}
    if "semantic_model" in tags and (".semanticmodel" in path_blob or ".tmdl" in path_blob):
        score += 3.0
    if "dashboard" in tags and (".report/" in path_blob or "report.json" in path_blob):
        score += 3.0
    if "paginated" in tags and ".rdl" in path_blob:
        score += 3.0
    support = pattern.get("support_count") or 1
    score += min(3.0, support / 20.0)
    return score


def predict_bot_risks(
    changed_paths: list[str],
    diff_excerpt: str = "",
    *,
    intelligence_path: Path | None = None,
    top_n: int = 12,
    min_score: float = 2.0,
) -> dict[str, Any]:
    """
    Rank learned bot patterns against this branch before PR is opened.
    Intelligence is learned from team corpus — not per-PR hardcoding.
    """
    intel = _load_intelligence(intelligence_path)
    blob = _path_blob(changed_paths)
    ranked: list[dict[str, Any]] = []
    for p in intel.get("patterns") or []:
        s = _score_pattern(p, blob, diff_excerpt)
        if s < min_score:
            continue
        ranked.append(
            {
                "score": round(s, 2),
                "pattern_id": p.get("pattern_id"),
                "likely_bot_finding": p.get("representative_title"),
                "why_it_happens": p.get("why_it_happens"),
                "do_before_opening_pr": p.get("preventive_action"),
                "learned_from_support": p.get("support_count"),
                "bot_sources": p.get("bot_sources"),
                "example_prs": (p.get("example_prs") or [])[:2],
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "intelligence_source": intel.get("source", "unknown"),
        "corpus_prs_analyzed": intel.get("prs_with_bot_analyzed"),
        "predictions": ranked[:top_n],
        "changed_paths_count": len(changed_paths),
    }


def format_preflight_block(result: dict) -> str:
    lines = [
        "BOT PREFLIGHT (learned from team closed PRs — Cursor + Circuit):",
        f"Corpus: {result.get('corpus_prs_analyzed')} bot PRs · paths in this branch: {result.get('changed_paths_count')}",
        "",
    ]
    preds = result.get("predictions") or []
    if not preds:
        lines.append("No strong match to historical bot patterns for these paths (still run scope preflight).")
        return "\n".join(lines)
    for i, p in enumerate(preds, 1):
        lines.append(f"{i}. [{p['score']}] {p['likely_bot_finding']}")
        lines.append(f"   Why: {p['why_it_happens']}")
        lines.append(f"   Fix before PR: {p['do_before_opening_pr']}")
        ex = p.get("example_prs") or []
        if ex:
            lines.append(f"   Seen on: {ex[0].get('url', '')}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Predict bot review risks from learned corpus")
    parser.add_argument("--paths-file", required=True)
    parser.add_argument("--diff-file", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    paths = [
        ln.strip()
        for ln in Path(args.paths_file).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    diff_excerpt = ""
    if args.diff_file and Path(args.diff_file).is_file():
        diff_excerpt = Path(args.diff_file).read_text(encoding="utf-8")[:50000]
    result = predict_bot_risks(paths, diff_excerpt)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_preflight_block(result))


if __name__ == "__main__":
    main()
