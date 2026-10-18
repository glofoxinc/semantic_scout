"""Semantic Scout intake — Jira text to scope matrix (universal, no static bundles)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.deliverables import infer_deliverable_globs, primary_artifact_glob
from lib.jira_requirement_matrix import (
    build_requirement_matrix,
    format_matrix_markdown,
    matrix_to_ticket_profile,
)
from lib.ticket_gap_report import format_ticket_list, run_bundle_report


def intake_from_text(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str = "",
    *,
    artifact_glob: str = "",
) -> dict:
    globs = infer_deliverable_globs(summary, description, comments_text)
    if not artifact_glob and globs:
        artifact_glob = primary_artifact_glob(globs)
    matrix = build_requirement_matrix(
        ticket_key=ticket_key,
        summary=summary,
        description=description,
        comments_text=comments_text,
    )
    profile = matrix_to_ticket_profile(
        ticket_key,
        summary,
        matrix,
        description=description,
        comments_text=comments_text,
        artifact_glob=artifact_glob,
    )
    return {
        "ticket_key": ticket_key,
        "profile": profile,
        "deliverable_globs": globs,
        "matrix_markdown": format_matrix_markdown(ticket_key, summary, matrix),
        "matrix": [m.as_dict() for m in matrix],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic Scout Jira intake")
    parser.add_argument("--key", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--description-file", type=Path)
    parser.add_argument("--comments-file", type=Path)
    parser.add_argument("--jira-json", type=Path, help="Exported Jira JSON from Atlassian MCP")
    parser.add_argument("--artifact-glob", default="")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    key = args.key.strip().upper()
    summary = args.summary
    description = ""
    comments = ""

    if args.jira_json and args.jira_json.is_file():
        raw = json.loads(args.jira_json.read_text(encoding="utf-8"))
        summary = summary or raw.get("summary") or ""
        description = raw.get("description") or ""
        comments = raw.get("comments_text") or ""

    if args.description_file:
        description = args.description_file.read_text(encoding="utf-8")
    if args.comments_file:
        comments = args.comments_file.read_text(encoding="utf-8")

    result = intake_from_text(
        key, summary, description, comments, artifact_glob=args.artifact_glob
    )
    print(result["matrix_markdown"])

    if args.out:
        bundle = {
            "schema_version": 2,
            "bundle_id": key,
            "tickets": [result["profile"]],
        }
        args.out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print(f"Wrote bundle: {args.out}")

    if args.repo_root:
        bundle_path = args.out or Path(f"scout-bundle-{key}.json")
        if not bundle_path.is_file():
            bundle_path.write_text(
                json.dumps(
                    {"schema_version": 2, "bundle_id": key, "tickets": [result["profile"]]},
                    indent=2,
                ),
                encoding="utf-8",
            )
        from lib.git_scope import git_changed_files, git_diff_excerpt

        reports = run_bundle_report(
            bundle_path,
            args.repo_root,
            branch_ctx={
                "base_ref": args.base_ref,
                "changed_paths": git_changed_files(args.repo_root, args.base_ref),
                "diff_excerpt": git_diff_excerpt(args.repo_root, args.base_ref),
                "scope_mode": "ticket",
            },
        )
        print(format_ticket_list(reports))


if __name__ == "__main__":
    main()
