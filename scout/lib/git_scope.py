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


def scope_violations(
    changed_paths: list[str],
    *,
    in_scope: list[str],
    out_of_scope: list[str],
) -> list[dict[str, str]]:
    """
    Flag paths on the branch that Jira did not authorize.
    in_scope entries are globs or path fragments from the ticket profile.
    """
    violations: list[dict[str, str]] = []
    if not changed_paths:
        return violations

    for path in changed_paths:
        norm = path.replace("\\", "/")
        if out_of_scope and _matches_any(norm, out_of_scope):
            violations.append(
                {
                    "path": norm,
                    "reason": "Matches ticket out-of-scope list",
                    "severity": "blocker",
                }
            )
            continue
        if in_scope and not _matches_any(norm, in_scope):
            # Allow common non-deliverable noise only when empty in_scope
            if any(
                seg in norm.lower()
                for seg in (".gitignore", "readme", "license")
            ):
                continue
            violations.append(
                {
                    "path": norm,
                    "reason": "Not listed in ticket in_scope — verify Jira or revert before PR",
                    "severity": "blocker",
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
