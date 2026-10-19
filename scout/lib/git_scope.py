"""Git diff scope for Semantic Scout (no external MCP)."""
from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


def _run_git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def git_current_branch(repo_root: Path) -> str:
    code, out, _ = _run_git(repo_root, "branch", "--show-current")
    if code != 0:
        return ""
    return (out or "").strip()


def git_changed_files(repo_root: Path, base_ref: str) -> list[str]:
    """Paths changed between base_ref and HEAD (POSIX-style relative paths)."""
    code, out, _ = _run_git(repo_root, "diff", "--name-only", f"{base_ref}...HEAD")
    if code != 0:
        code, out, _ = _run_git(repo_root, "diff", "--name-only", base_ref, "HEAD")
    lines = [ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()]
    return lines


def git_diff_excerpt(repo_root: Path, base_ref: str, max_bytes: int = 80_000) -> str:
    code, out, _ = _run_git(repo_root, "diff", f"{base_ref}...HEAD")
    if code != 0:
        code, out, _ = _run_git(repo_root, "diff", base_ref, "HEAD")
    return out[:max_bytes]


def _matches_any(path: str, patterns: list[str]) -> bool:
    low = path.replace("\\", "/").lower()
    file_name = Path(path).name.lower()
    for pat in patterns:
        p = pat.replace("\\", "/")
        pl = p.lower()
        if fnmatch.fnmatch(low, pl) or fnmatch.fnmatch(file_name, pl):
            return True
        if fnmatch.fnmatch(low, f"**/{Path(p).name.lower()}"):
            return True
        if Path(p).name.lower() == file_name:
            return True
        if pl.lstrip("*").strip("/") in low:
            return True
    return False


def deliverable_name_roots(in_scope: list[str]) -> list[str]:
    roots: list[str] = []
    for pat in in_scope:
        stem = Path(pat.replace("**/", "").replace("*/", "")).stem
        if stem and stem not in ("*", "*.rdl"):
            roots.append(stem.lower())
    return roots


def _is_bi_artifact(path: str) -> bool:
    low = path.lower()
    return any(
        ext in low
        for ext in (
            ".rdl",
            ".tmdl",
            "report.json",
            ".pbir",
            ".paginatedreport/",
            ".semanticmodel/",
            ".report/",
        )
    )


def scope_violations(
    changed_paths: list[str],
    *,
    in_scope: list[str],
    out_of_scope: list[str],
    scope_mode: str = "ticket",
) -> list[dict[str, str]]:
    """
    Flag paths on the branch that Jira did not authorize.
    scope_mode:
      ticket — other BI files on branch are warnings (multi-ticket branches)
      strict — every changed BI path must match in_scope
    """
    violations: list[dict[str, str]] = []
    if not changed_paths:
        return violations

    roots = deliverable_name_roots(in_scope)
    strict = scope_mode == "strict"

    for path in changed_paths:
        norm = path.replace("\\", "/")
        low = norm.lower()
        if out_of_scope and _matches_any(norm, out_of_scope):
            violations.append(
                {
                    "path": norm,
                    "reason": "Matches ticket out-of-scope list",
                    "severity": "blocker",
                }
            )
            continue
        if any(seg in low for seg in (".gitignore", "readme", "license", ".github/")):
            continue
        if not _is_bi_artifact(norm):
            continue
        if in_scope and _matches_any(norm, in_scope):
            continue
        if roots and any(root in low for root in roots):
            continue
        if in_scope and not _matches_any(norm, in_scope):
            violations.append(
                {
                    "path": norm,
                    "reason": (
                        "Not this ticket's deliverable — split PR or confirm bundle ticket"
                        if not strict
                        else "Not listed in ticket in_scope — revert before PR"
                    ),
                    "severity": "blocker" if strict else "info",
                }
            )
    return violations


def format_scope_report(violations: list[dict[str, str]]) -> str:
    if not violations:
        return "SCOPE: all changed paths align with ticket in_scope."
    lines = ["SCOPE VIOLATIONS (fix or get Jira override before PR):"]
    for v in violations:
        lines.append(f"  [{v['severity']}] {v['path']} — {v['reason']}")
    return "\n".join(lines)
