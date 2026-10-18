"""Resolve glofoxinc GitHub repo from Jira key + title (AN/PIC routing)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "glofox-repo-jira-exemplars.json"

FABRIC_KEYWORDS = (
    "fabric",
    "lakehouse",
    "gold layer",
    "databricks",
    "notebook",
    "ingestion",
    "pipeline",
)

GITHUB_URL_RE = re.compile(
    r"github\.com/(?P<org>[^/]+)/(?P<repo>[^/\s#]+)",
    re.IGNORECASE,
)
JIRA_KEY_RE = re.compile(r"^(AN|PIC)-\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class RouteResult:
    github: str
    client_display_name: str
    scope: str
    confidence: str  # high | medium | low
    reason: str
    integration_branch: str
    branch_patterns: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "github": self.github,
            "client_display_name": self.client_display_name,
            "scope": self.scope,
            "confidence": self.confidence,
            "reason": self.reason,
            "integration_branch": self.integration_branch,
            "branch_patterns": list(self.branch_patterns),
        }


def _load_catalog() -> dict:
    with DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _fabric_signal(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in FABRIC_KEYWORDS)


def _explicit_github(text: str) -> str | None:
    m = GITHUB_URL_RE.search(text or "")
    if not m:
        return None
    return f"{m.group('org')}/{m.group('repo')}"


def _match_repo_by_keywords(summary: str, description: str, catalog: dict) -> tuple[dict | None, str, str]:
    blob = f"{summary}\n{description or ''}"
    if _fabric_signal(blob):
        for repo in catalog.get("repos", []):
            if repo.get("github", "").endswith("gf-fabric-fitnessbi"):
                return repo, "high", "Fabric/lakehouse/notebook keywords in ticket text"

    best: dict | None = None
    best_kw = ""
    for repo in catalog.get("repos", []):
        if repo.get("scope") != "custom_client":
            continue
        for kw in repo.get("titleKeywords", []):
            if kw and kw.lower() in summary.lower():
                if len(kw) > len(best_kw):
                    best = repo
                    best_kw = kw
    if best:
        return best, "high", f"Matched client keyword '{best_kw}' in summary"

    return None, "low", "No client keyword match"


def integration_branch_for(github: str) -> str:
    if github.endswith("gf-insights-fitnessbi"):
        return "Standard_dev"
    return "main"


def branch_patterns_for(jira_key: str) -> tuple[str, ...]:
    key = jira_key.upper()
    return (
        f"feature/{key}-*",
        f"{key}-*",
        f"feature/{key}*",
        key,
    )


def resolve_route(
    jira_key: str,
    summary: str = "",
    description: str = "",
) -> RouteResult:
    """Return primary GitHub repo for a Jira ticket."""
    catalog = _load_catalog()
    key = (jira_key or "").strip().upper()
    if not JIRA_KEY_RE.match(key):
        raise ValueError(f"Unsupported Jira key: {jira_key!r} (expected AN-* or PIC-*)")

    project = key.split("-")[0]
    combined = f"{summary}\n{description or ''}"
    explicit = _explicit_github(combined)
    if explicit:
        for repo in catalog.get("repos", []):
            if repo.get("github", "").lower() == explicit.lower():
                gh = repo["github"]
                return RouteResult(
                    github=gh,
                    client_display_name=repo.get("clientDisplayName", gh),
                    scope=repo.get("scope", "unknown"),
                    confidence="high",
                    reason=f"Explicit GitHub URL in ticket → {gh}",
                    integration_branch=integration_branch_for(gh),
                    branch_patterns=branch_patterns_for(key),
                )
        return RouteResult(
            github=explicit,
            client_display_name=explicit,
            scope="explicit_url",
            confidence="medium",
            reason=f"Explicit GitHub URL in ticket (not in catalog): {explicit}",
            integration_branch="main",
            branch_patterns=branch_patterns_for(key),
        )

    if project == "AN" and not _fabric_signal(combined):
        for repo in catalog.get("repos", []):
            if repo.get("github") == "glofoxinc/gf-insights-fitnessbi":
                gh = repo["github"]
                return RouteResult(
                    github=gh,
                    client_display_name=repo.get("clientDisplayName", gh),
                    scope=repo.get("scope", "standard_analyze"),
                    confidence="high",
                    reason="AN-* default → Glofox Analytics standard repo (no Fabric override)",
                    integration_branch=integration_branch_for(gh),
                    branch_patterns=branch_patterns_for(key),
                )

    if _fabric_signal(combined):
        for repo in catalog.get("repos", []):
            if repo.get("github", "").endswith("gf-fabric-fitnessbi"):
                gh = repo["github"]
                return RouteResult(
                    github=gh,
                    client_display_name=repo.get("clientDisplayName", gh),
                    scope=repo.get("scope", "fabric_data"),
                    confidence="high",
                    reason="Fabric/lakehouse work → gf-fabric-fitnessbi",
                    integration_branch=integration_branch_for(gh),
                    branch_patterns=branch_patterns_for(key),
                )

    matched, conf, reason = _match_repo_by_keywords(summary, description or "", catalog)
    if matched:
        gh = matched["github"]
        return RouteResult(
            github=gh,
            client_display_name=matched.get("clientDisplayName", gh),
            scope=matched.get("scope", "custom_client"),
            confidence=conf,
            reason=reason,
            integration_branch=integration_branch_for(gh),
            branch_patterns=branch_patterns_for(key),
        )

    if project == "PIC":
        fallback = "glofoxinc/gf-insights-fitnessbi"
        return RouteResult(
            github=fallback,
            client_display_name="Unknown PIC client — verify manually",
            scope="unknown",
            confidence="low",
            reason="PIC-* with no keyword match; confirm client in summary/description",
            integration_branch=integration_branch_for(fallback),
            branch_patterns=branch_patterns_for(key),
        )

    gh = "glofoxinc/gf-insights-fitnessbi"
    return RouteResult(
        github=gh,
        client_display_name="Glofox Analytics (fallback)",
        scope="standard_analyze",
        confidence="low",
        reason="Fallback to standard repo",
        integration_branch=integration_branch_for(gh),
        branch_patterns=branch_patterns_for(key),
    )


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Resolve glofox GitHub repo from Jira ticket")
    parser.add_argument("jira_key", help="e.g. AN-5192 or PIC-6297")
    parser.add_argument("--summary", default="", help="Jira summary line")
    parser.add_argument("--description", default="", help="Optional description excerpt")
    args = parser.parse_args()
    try:
        result = resolve_route(args.jira_key, args.summary, args.description)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(result.as_dict(), indent=2))


if __name__ == "__main__":
    main()
