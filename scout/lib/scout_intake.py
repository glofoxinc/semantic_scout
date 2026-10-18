"""Semantic Scout intake — Jira to scope matrix + optional gap report (skill accelerator)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.jira_requirement_matrix import (
    build_requirement_matrix,
    format_matrix_markdown,
    infer_artifact_glob_from_summary,
    load_jira_from_paginate,
    matrix_to_ticket_profile,
)
from lib.ticket_gap_report import format_ticket_list, run_bundle_report


def intake_from_text(
    ticket_key: str,
    summary: str,
    description: str,
    comments_text: str = "",
    *,
    artifact_glob: str = "**/*.rdl",
) -> dict:
    if artifact_glob in ("", "**/*.rdl"):
        inferred = infer_artifact_glob_from_summary(summary, description)
        if inferred:
            artifact_glob = inferred
    matrix = build_requirement_matrix(
        ticket_key=ticket_key,
        summary=summary,
        description=description,
        comments_text=comments_text,
    )
    profile = matrix_to_ticket_profile(
        ticket_key, summary, matrix, artifact_glob=artifact_glob
    )
    return {
        "ticket_key": ticket_key,
        "profile": profile,
        "matrix_markdown": format_matrix_markdown(ticket_key, summary, matrix),
        "matrix": [m.as_dict() for m in matrix],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic Scout Jira intake")
    parser.add_argument("--key", required=True, help="AN-5605 or PIC-1234")
    parser.add_argument("--summary", default="")
    parser.add_argument("--description-file", type=Path)
    parser.add_argument("--comments-file", type=Path)
    parser.add_argument("--jira-json", type=Path, help="Exported fetch_jira_ticket JSON")
    parser.add_argument("--fetch", action="store_true", help="Try Paginate jira_intake fetch")
    parser.add_argument("--artifact-glob", default="**/*.rdl")
    parser.add_argument("--repo-root", type=Path, help="Run gap report after intake")
    parser.add_argument("--live-paginate", action="store_true")
    parser.add_argument("--out", type=Path, help="Write bundle JSON for ticket_gap_report")
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
    elif args.fetch:
        raw = load_jira_from_paginate(key)
        if not raw.get("ok"):
            print(json.dumps(raw, indent=2))
            raise SystemExit(1)
        summary = summary or raw.get("summary") or ""
        description = raw.get("description") or ""
        comments = raw.get("comments_text") or ""

    if args.description_file:
        description = args.description_file.read_text(encoding="utf-8")
    if args.comments_file:
        comments = args.comments_file.read_text(encoding="utf-8")

    if not summary and not description:
        print(
            "Provide --summary + --description-file, --jira-json, or --fetch with Jira credentials."
        )
        raise SystemExit(2)

    result = intake_from_text(
        key,
        summary,
        description,
        comments,
        artifact_glob=args.artifact_glob,
    )
    print(result["matrix_markdown"])
    print()

    if args.out:
        bundle = {
            "schema_version": 2,
            "bundle_id": key,
            "tickets": [result["profile"]],
            "default_out_of_scope": [
                "Power BI dashboard unless listed in matrix",
                "Semantic model unless listed in matrix",
            ],
            "default_ignore_standards_ids": [
                "date_defaults_from_logic_mismatch",
                "missing_vertical_align",
                "page_width_out_of_range",
                "dataset_overlap",
                "mainquery_missing_business_params",
                "country_branch_dataset_drift",
                "identity_no_ticket",
            ],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print(f"Wrote bundle: {args.out}")

    if args.repo_root and args.out:
        reports = run_bundle_report(
            args.out,
            args.repo_root,
            paginate_by_ticket=None,
            process_ctx={"pbrs_signed_off": False},
        )
        if args.live_paginate:
            from lib.paginate_audit_bridge import run_paginate_full_audit
            from lib.ticket_gap_report import _find_artifact

            pmap = {}
            for profile in [result["profile"]]:
                art = _find_artifact(args.repo_root, profile.get("artifact_glob", "**/*.rdl"))
                if art:
                    pmap[profile["key"]] = run_paginate_full_audit(art, profile["key"])
            reports = run_bundle_report(
                args.out,
                args.repo_root,
                paginate_by_ticket=pmap,
                process_ctx={"pbrs_signed_off": False},
            )
        print(format_ticket_list(reports))


if __name__ == "__main__":
    main()
