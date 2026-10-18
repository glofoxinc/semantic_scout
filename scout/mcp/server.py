#!/usr/bin/env python3
"""MCP server — Semantic Scout (stdio). Universal Jira + git + bot preflight only."""
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
from lib.deliverables import infer_deliverable_globs
from lib.git_scope import format_scope_report, git_changed_files, git_diff_excerpt, scope_violations
from lib.jira_repo_router import resolve_route
from lib.review_output import build_review_summary
from lib.scout_intake import intake_from_text
from lib.signoff_gate import run_signoff_checks
from lib.ticket_gap_report import format_ticket_list, run_bundle_report

SCOUT_VERSION = "5.0.0"

mcp = MCPServer("semantic-scout")


def _bundle_from_jira(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str,
    artifact_glob: str,
) -> tuple[dict, Path]:
    intake = intake_from_text(
        ticket_key.strip().upper(),
        summary,
        description,
        comments_text,
        artifact_glob=artifact_glob,
    )
    bundle = {
        "schema_version": 2,
        "bundle_id": ticket_key.strip().upper(),
        "tickets": [intake["profile"]],
        "default_out_of_scope": [
            "scripts/ unless Jira names them",
            "docs/ unless Jira names them",
            ".github/ unless Jira names them",
        ],
    }
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(bundle, tmp, indent=2)
    tmp.close()
    return intake, Path(tmp.name)


@mcp.tool()
def scout_engine_health() -> str:
    """Engine sign-off (universal matrix + deliverable inference)."""
    return json.dumps({**run_signoff_checks(), "scout_version": SCOUT_VERSION}, indent=2)


@mcp.tool()
def scout_route_repository(
    ticket_key: str,
    summary: str = "",
    description: str = "",
) -> str:
    route = resolve_route(ticket_key, summary, description)
    return json.dumps(route.as_dict(), indent=2)


@mcp.tool()
def scout_requirement_matrix(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str = "",
    artifact_glob: str = "",
) -> str:
    """Jira text → matrix + profile (no static ticket bundles)."""
    result = intake_from_text(
        ticket_key.strip().upper(),
        summary,
        description,
        comments_text,
        artifact_glob=artifact_glob,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def scout_branch_diff(repo_root: str, base_ref: str = "origin/main") -> str:
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
            "diff_excerpt": excerpt[:50_000],
        },
        indent=2,
    )


@mcp.tool()
def scout_bot_ahead(changed_paths_json: str, diff_excerpt: str = "") -> str:
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
    artifact_glob: str = "",
    head_sha: str = "",
    circuit_reviewed_sha: str = "",
    scope_mode: str = "ticket",
) -> str:
    """
    Full review from Jira text + git diff only. No Paginate, no static ticket JSON.
    Pass artifact_glob when Jira does not name the file (e.g. **/My Report.rdl).
    """
    root = Path(repo_root).resolve()
    if not root.is_dir():
        return json.dumps({"ok": False, "error": f"repo_root not found: {root}"})

    intake, bundle_file = _bundle_from_jira(
        ticket_key, summary, description, comments_text, artifact_glob
    )
    changed_paths = git_changed_files(root, base_ref)
    diff_excerpt = git_diff_excerpt(root, base_ref)
    branch_ctx = {
        "base_ref": base_ref,
        "changed_paths": changed_paths,
        "diff_excerpt": diff_excerpt,
        "head_sha": head_sha or None,
        "circuit_reviewed_sha": circuit_reviewed_sha or None,
        "scope_mode": scope_mode,
    }
    process_ctx: dict = {}
    if head_sha or circuit_reviewed_sha:
        process_ctx["head_sha"] = head_sha
        process_ctx["circuit_reviewed_sha"] = circuit_reviewed_sha

    reports = run_bundle_report(
        bundle_file,
        root,
        process_ctx=process_ctx,
        branch_ctx=branch_ctx,
    )

    profile = intake["profile"]
    scope = profile.get("scope") or {}
    in_scope = list(dict.fromkeys(scope.get("in_scope") or []))
    if not in_scope and artifact_glob:
        in_scope = [artifact_glob]
    violations = scope_violations(
        changed_paths,
        in_scope=in_scope,
        out_of_scope=list(scope.get("out_of_scope") or []),
        scope_mode=scope_mode,
    )
    bot = run_bot_preflight(changed_paths, diff_excerpt)
    circuit_stale = bool(
        head_sha and circuit_reviewed_sha and head_sha != circuit_reviewed_sha
    )
    summary_obj = build_review_summary(
        ticket_key=ticket_key.strip().upper(),
        matrix_markdown=intake["matrix_markdown"],
        scope_violations=violations,
        bot_predictions=bot.get("predictions") or [],
        reports=reports,
        changed_paths=changed_paths,
        circuit_stale=circuit_stale,
    )

    return json.dumps(
        {
            "ok": True,
            "scout_version": SCOUT_VERSION,
            "deliverable_globs": infer_deliverable_globs(
                summary, description, comments_text
            ),
            "review": summary_obj,
            "matrix_markdown": intake["matrix_markdown"],
            "scope_report": format_scope_report(violations),
            "bot_ahead_markdown": format_preflight_block(bot),
            "gap_markdown": format_ticket_list(reports),
            "reports": [r.as_dict() for r in reports],
        },
        indent=2,
    )


@mcp.tool()
def scout_gap_report(
    repo_root: str,
    ticket_key: str,
    summary: str = "",
    description: str = "",
    comments_text: str = "",
    bundle_path: str | None = None,
    artifact_glob: str = "",
    base_ref: str = "origin/main",
) -> str:
    if bundle_path:
        return json.dumps(
            {
                "ok": False,
                "error": "bundle_path is deprecated; pass Jira text to scout_ticket_review",
            }
        )
    return scout_ticket_review(
        repo_root=repo_root,
        ticket_key=ticket_key,
        summary=summary,
        description=description,
        comments_text=comments_text,
        base_ref=base_ref,
        artifact_glob=artifact_glob,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
