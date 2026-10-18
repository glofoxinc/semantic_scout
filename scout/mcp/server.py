#!/usr/bin/env python3
"""MCP server — Semantic Scout (stdio, mcp SDK 2.x). Independent Jira + git + bot preflight."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer

from lib.bot_preflight import format_preflight_block, run_bot_preflight
from lib.git_scope import format_scope_report, git_changed_files, git_diff_excerpt, scope_violations
from lib.jira_repo_router import resolve_route
from lib.scout_intake import intake_from_text
from lib.signoff_gate import run_signoff_checks
from lib.ticket_gap_report import format_ticket_list, run_bundle_report

mcp = MCPServer("semantic-scout")

_PROFILES = ROOT / "data" / "ticket_profiles"


def _default_bundle_dict(profile: dict) -> dict:
    key = profile.get("key") or profile.get("ticket_key") or "TICKET"
    return {
        "schema_version": 2,
        "bundle_id": key,
        "tickets": [profile],
        "default_out_of_scope": [
            "Power BI dashboard unless listed in matrix",
            "Semantic model unless listed in matrix",
            "scripts/ unless ticket names automation",
            "docs/ unless ticket names documentation deliverable",
        ],
    }


def _bundle_path_for_ticket(ticket_key: str) -> Path | None:
    key = ticket_key.strip().upper()
    if not _PROFILES.is_dir():
        return None
    for path in sorted(_PROFILES.glob("*.json")):
        if key in path.stem or key in path.read_text(encoding="utf-8"):
            return path
    return None


def _resolve_bundle(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str,
    artifact_glob: str,
    bundle_path: str | None,
) -> Path | None:
    if bundle_path:
        return Path(bundle_path)
    found = _bundle_path_for_ticket(ticket_key)
    if found:
        return found
    if not (summary or description):
        return None
    intake = intake_from_text(
        ticket_key.strip().upper(),
        summary,
        description,
        comments_text,
        artifact_glob=artifact_glob,
    )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(_default_bundle_dict(intake["profile"]), tmp, indent=2)
    tmp.close()
    return Path(tmp.name)


@mcp.tool()
def scout_engine_health() -> str:
    """Run Scout sign-off checks (matrix + scoped evaluation logic)."""
    return json.dumps(run_signoff_checks(), indent=2)


@mcp.tool()
def scout_route_repository(
    ticket_key: str,
    summary: str = "",
    description: str = "",
) -> str:
    """Suggest glofoxinc GitHub repo and integration branch from Jira key + text."""
    route = resolve_route(ticket_key, summary, description)
    return json.dumps(route.as_dict(), indent=2)


@mcp.tool()
def scout_requirement_matrix(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str = "",
    artifact_glob: str = "**/*.rdl",
) -> str:
    """Jira text → numbered requirement matrix + ticket profile JSON."""
    result = intake_from_text(
        ticket_key.strip().upper(),
        summary,
        description,
        comments_text,
        artifact_glob=artifact_glob,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def scout_branch_diff(
    repo_root: str,
    base_ref: str = "origin/main",
) -> str:
    """List changed files and diff excerpt vs base (for scope + bot preflight)."""
    root = Path(repo_root).resolve()
    if not root.is_dir():
        return json.dumps({"ok": False, "error": f"repo_root not found: {root}"})
    paths = git_changed_files(root, base_ref)
    excerpt = git_diff_excerpt(root, base_ref)
    return json.dumps(
        {
            "ok": True,
            "base_ref": base_ref,
            "changed_paths": paths,
            "diff_excerpt_chars": len(excerpt),
            "diff_excerpt": excerpt[:50_000],
        },
        indent=2,
    )


@mcp.tool()
def scout_bot_ahead(
    changed_paths_json: str,
    diff_excerpt: str = "",
) -> str:
    """
    Predict Circuit / review bot comments from learned corpus + this branch diff.
    Pass changed_paths as JSON array of strings (from scout_branch_diff).
    """
    try:
        paths = json.loads(changed_paths_json)
        if not isinstance(paths, list):
            raise ValueError("expected JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": str(exc)})
    result = run_bot_preflight([str(p) for p in paths], diff_excerpt)
    return json.dumps(
        {
            "ok": True,
            "predictions": result.get("predictions"),
            "markdown": format_preflight_block(result),
            "corpus_prs_analyzed": result.get("corpus_prs_analyzed"),
        },
        indent=2,
    )


@mcp.tool()
def scout_ticket_review(
    repo_root: str,
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str = "",
    base_ref: str = "origin/main",
    artifact_glob: str = "**/*.rdl",
    bundle_path: str | None = None,
    head_sha: str = "",
    circuit_reviewed_sha: str = "",
) -> str:
    """
    Full Semantic Scout run: matrix-backed profile, git scope, per-requirement evidence,
    delivery ratings, bot-ahead. No Paginate Forge required.
    """
    root = Path(repo_root).resolve()
    if not root.is_dir():
        return json.dumps({"ok": False, "error": f"repo_root not found: {root}"})

    intake = intake_from_text(
        ticket_key.strip().upper(),
        summary,
        description,
        comments_text,
        artifact_glob=artifact_glob,
    )
    bundle_file = _resolve_bundle(
        ticket_key, summary, description, comments_text, artifact_glob, bundle_path
    )
    if not bundle_file or not bundle_file.is_file():
        return json.dumps({"ok": False, "error": "Could not build ticket bundle"})

    changed_paths = git_changed_files(root, base_ref)
    diff_excerpt = git_diff_excerpt(root, base_ref)
    branch_ctx = {
        "base_ref": base_ref,
        "changed_paths": changed_paths,
        "diff_excerpt": diff_excerpt,
        "head_sha": head_sha or None,
        "circuit_reviewed_sha": circuit_reviewed_sha or None,
    }
    process_ctx: dict = {}
    if head_sha or circuit_reviewed_sha:
        process_ctx["head_sha"] = head_sha
        process_ctx["circuit_reviewed_sha"] = circuit_reviewed_sha

    reports = run_bundle_report(
        bundle_file,
        root,
        paginate_by_ticket=None,
        process_ctx=process_ctx,
        branch_ctx=branch_ctx,
    )

    profile = intake["profile"]
    scope = profile.get("scope") or {}
    in_scope = list(scope.get("in_scope") or [])
    if profile.get("artifact_glob"):
        in_scope.append(profile["artifact_glob"])
    violations = scope_violations(
        changed_paths,
        in_scope=in_scope,
        out_of_scope=list(scope.get("out_of_scope") or []),
    )

    bot = run_bot_preflight(changed_paths, diff_excerpt)

    payload = {
        "ok": True,
        "ticket_key": ticket_key.strip().upper(),
        "matrix_markdown": intake["matrix_markdown"],
        "scope_report": format_scope_report(violations),
        "bot_ahead_markdown": format_preflight_block(bot),
        "changed_paths": changed_paths,
        "gap_markdown": format_ticket_list(reports),
        "reports": [r.as_dict() for r in reports],
    }
    return json.dumps(payload, indent=2)


@mcp.tool()
def scout_gap_report(
    repo_root: str,
    ticket_key: str,
    summary: str = "",
    description: str = "",
    comments_text: str = "",
    bundle_path: str | None = None,
    artifact_glob: str = "**/*.rdl",
    base_ref: str = "origin/main",
) -> str:
    """Delivery gap report (use scout_ticket_review for matrix + bot + scope in one call)."""
    return scout_ticket_review(
        repo_root=repo_root,
        ticket_key=ticket_key,
        summary=summary,
        description=description,
        comments_text=comments_text,
        base_ref=base_ref,
        artifact_glob=artifact_glob,
        bundle_path=bundle_path,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
