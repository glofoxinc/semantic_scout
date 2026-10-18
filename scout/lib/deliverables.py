"""Universal deliverable inference from any Jira ticket text (no static bundles)."""
from __future__ import annotations

import re
from pathlib import Path


def infer_deliverable_globs(summary: str, description: str = "", comments_text: str = "") -> list[str]:
    """
    Derive in-scope path globs from ticket text only.
    Supports paginated (.rdl), dashboard (.Report), semantic model (.tmdl), explicit paths.
    """
    text = f"{summary}\n{description}\n{comments_text}"
    globs: list[str] = []

    for match in re.finditer(r"[-–]\s*(.+?)\s*\(paginated\)", text, re.I):
        name = match.group(1).strip()
        if name and len(name) < 120:
            globs.append(f"**/{name}.rdl")

    for match in re.finditer(r"[-–]\s*(.+?)\s*\(dashboard\)", text, re.I):
        name = match.group(1).strip()
        if name:
            globs.append(f"**/*{name}*.Report/**/report.json")
            globs.append(f"**/{name}.Report/**/report.json")

    if re.search(r"\bsemantic\s+model\b|\.tmdl\b|\.semanticmodel\b", text, re.I):
        globs.append("**/*.SemanticModel/**/*.tmdl")
        globs.append("**/*.tmdl")

    for match in re.finditer(
        r"(?i)(?:^|[\s'\"])([A-Za-z0-9][\w\s\-]{2,80}?\.(?:rdl|tmdl))\b",
        text,
    ):
        fname = match.group(1).strip()
        globs.append(f"**/{fname}")

    for match in re.finditer(
        r"`([^`]+\.(?:rdl|tmdl|json))`|\"([^\"]+\.(?:rdl|tmdl|json))\"",
        text,
    ):
        fname = (match.group(1) or match.group(2) or "").strip()
        if fname:
            globs.append(f"**/{Path(fname).name}")

    if re.search(r"\breport\.json\b", text, re.I):
        globs.append("**/*.Report/**/report.json")

    seen: set[str] = set()
    out: list[str] = []
    for g in globs:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out


def primary_artifact_glob(globs: list[str]) -> str:
    if globs:
        return globs[0]
    return ""
