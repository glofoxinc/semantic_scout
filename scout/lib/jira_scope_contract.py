"""Build a Jira-first scope contract from ticket profiles and branch evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

EvidenceStatus = Literal["present", "absent", "partial", "unverified", "out_of_scope"]


@dataclass
class ScopeLine:
    category: Literal["artifact", "requirement", "excluded", "process"]
    label: str
    status: EvidenceStatus
    evidence: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "label": self.label,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass
class ScopeContract:
    bundle_id: str
    ticket_key: str
    deliverable_one_liner: str
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    lines: list[ScopeLine] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "ticket_key": self.ticket_key,
            "deliverable_one_liner": self.deliverable_one_liner,
            "in_scope": self.in_scope,
            "out_of_scope": self.out_of_scope,
            "lines": [ln.as_dict() for ln in self.lines],
        }


def deliverable_one_liner(profile: dict[str, Any]) -> str:
    custom = (profile.get("scope") or {}).get("deliverable")
    if custom:
        return str(custom).strip()
    reqs = profile.get("requirements") or []
    if reqs:
        return f"{profile.get('key', '')}: {reqs[0].get('text', profile.get('summary', ''))}"
    return str(profile.get("summary") or "Unspecified deliverable")


def build_scope_contract(
    bundle: dict[str, Any],
    profile: dict[str, Any],
    *,
    artifact_path: Path | None,
    requirement_status: dict[str, str],
) -> ScopeContract:
    """Map Jira profile + on-disk artifact to an implementation inventory."""
    scope = profile.get("scope") or {}
    in_scope = list(scope.get("in_scope") or [])
    if not in_scope and profile.get("artifact_glob"):
        in_scope.append(str(profile["artifact_glob"]))
    out_of_scope = list(scope.get("out_of_scope") or bundle.get("default_out_of_scope") or [])

    lines: list[ScopeLine] = []
    if artifact_path and artifact_path.is_file():
        lines.append(
            ScopeLine(
                category="artifact",
                label=profile.get("artifact_glob", artifact_path.name),
                status="present",
                evidence=str(artifact_path),
            )
        )
    else:
        lines.append(
            ScopeLine(
                category="artifact",
                label=profile.get("artifact_glob", "deliverable"),
                status="absent",
                evidence="No matching file on branch for artifact_glob",
            )
        )

    for req in profile.get("requirements") or []:
        rid = req.get("id", "")
        st = requirement_status.get(rid, "unverified")
        ev_status: EvidenceStatus
        if st == "met":
            ev_status = "present"
        elif st == "missing":
            ev_status = "absent"
        elif st == "partial":
            ev_status = "partial"
        else:
            ev_status = "unverified"
        lines.append(
            ScopeLine(
                category="requirement",
                label=req.get("text", rid),
                status=ev_status,
                evidence=f"requirement_id={rid}; automated_status={st}",
            )
        )

    for excluded in out_of_scope:
        lines.append(
            ScopeLine(
                category="excluded",
                label=excluded,
                status="out_of_scope",
                evidence="Not in Jira AC for this ticket — do not score as delivery miss",
            )
        )

    return ScopeContract(
        bundle_id=str(bundle.get("bundle_id") or ""),
        ticket_key=str(profile.get("key") or ""),
        deliverable_one_liner=deliverable_one_liner(profile),
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        lines=lines,
    )


def format_scope_contract(contract: ScopeContract) -> str:
    rows: list[str] = [
        "SCOPE CONTRACT (Jira-first — catalogue rules are separate)",
        f"Deliverable: {contract.deliverable_one_liner}",
    ]
    if contract.in_scope:
        rows.append("In scope:")
        for item in contract.in_scope:
            rows.append(f"  - {item}")
    if contract.out_of_scope:
        rows.append("Explicitly out of scope:")
        for item in contract.out_of_scope:
            rows.append(f"  - {item}")
    rows.append("Implementation inventory:")
    for ln in contract.lines:
        rows.append(f"  [{ln.status}] ({ln.category}) {ln.label}")
        if ln.evidence:
            rows.append(f"      {ln.evidence}")
    return "\n".join(rows)
