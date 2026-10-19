# Semantic Scout MCP — Requirements (highlighted)

## 1. Goal

Give the team an on-demand pre-PR validation tool that verifies Jira ticket work is complete on the feature branch before anyone opens a pull request.

---

## 2. Core requirements

### REQ-01 — Jira ticket integration

Read the ticket's summary, description, acceptance criteria, and comments for any supported **AN** or **PIC** ticket.

### REQ-02 — Artifact scope inference

Automatically identify required artifacts, including:

- Dashboards
- Paginated reports (RDL)
- Semantic models
- Documentation and companion files, when required

### REQ-03 — Acceptance criteria vs. Git diff

Compare every acceptance criterion against the actual feature-branch changes. Each criterion must have a clear **MET** / **MISSING** status and supporting file references.

### REQ-04 — Scoring and readiness

Calculate and display:

- Jira coverage score
- Branch hygiene score
- Overall readiness status: **READY** / **NOT READY**

### REQ-05 — Missing work and review feedback

Identify missing artifacts, incomplete criteria, scope issues, documentation gaps, parity issues, and likely reviewer or bot feedback.

### REQ-06 — Cursor-friendly remediation

Give developers actionable findings so they can fix gaps directly in Cursor before creating a PR.

---

## 3. Setup and daily workflow

### REQ-07 — One-time machine setup

Provide a reusable **Setup Semantic Scout** process. Developers should not need to repeat configuration for each ticket.

### REQ-08 — Simple on-demand command

The daily workflow should be as simple as:

**Semantic Scout for AN-XXXX**

(Replace `AN-XXXX` with the actual Jira ticket key.)

### REQ-09 — Review card before PR

Generate a consistent review card with criterion-level results, file evidence, scores, missing items, branch hygiene findings, and a readiness decision.

**Important constraint:** No per-ticket checklists and no one-off scripts committed to feature branches. Semantic Scout provides the repeatable validation workflow centrally.

---

## 4. What the review card must show

```
Semantic Scout Review
Ticket: AN-XXXX · Feature branch: <current branch>

Jira coverage        — <score> (from criteria evidence)
Branch hygiene       — <score> (from branch checks)

Acceptance criteria
  MET     — Dashboard changes implemented
            Evidence: <changed dashboard files>
  MISSING — Required semantic model update
            Evidence: no sufficient supporting diff identified
  MISSING — Documentation or parity requirement
            Evidence: required change not verified

Additional findings
  · Missing companion artifacts
  · Unrelated or out-of-scope changes
  · Potential reviewer or bot feedback
  · Suggested fixes and relevant file paths

Readiness gate
  READY only when configured requirements and mandatory checks pass.
```

*Illustrative layout. Scores and results must be calculated from actual Jira and Git data.*

---

## 5. Key quality and acceptance requirements

| ID | Requirement | Success condition |
|----|-------------|-----------------|
| **AC-01** | Ticket coverage | Any supported AN or PIC ticket can be reviewed on demand. |
| **AC-02** | Traceability | Every acceptance criterion has MET or MISSING with file evidence or an explicit evidence gap. |
| **AC-03** | Scope validation | Expected dashboards, RDLs, models, documentation, and companion artifacts are identified. |
| **AC-04** | Branch hygiene | Relevant branch changes are checked for scope and repository-specific issues. |
| **AC-05** | Actionable output | Missing work and likely review feedback are surfaced before PR creation. |
| **AC-06** | Readiness decision | A consistent READY / NOT READY result is displayed with reasons. |
| **AC-07** | Reusable setup | **Setup Semantic Scout** is performed once per machine (re-run only when config changes). |
| **AC-08** | Minimal daily effort | Developers invoke the review using the ticket key only — no ticket-specific checklists or scripts on the branch. |
| **AC-09** | Repeatability | Developers can rerun the review after DAX, RDL, filter, model, or documentation changes. |

---

## 6. Where Semantic Scout should be used

| Use case | When |
|----------|------|
| **Pre-PR gate** | Validate every dashboard, paginated report, or semantic model change. |
| **Regression validation** | Rerun after DAX, RDL, filters, or documentation edits. |
| **Ticket kickoff** | Establish expected artifacts and scope before development goes too far. |
| **Self-service review** | Verify completeness without waiting for reviewers during sprint crunch. |

---

## 7. MCP response structure (v1)

Successful `scout_ticket_review` returns: `ok`, `scout_version`, `response_schema_version` (**1.0**), `readiness`, `confidence`, `review_card_markdown`, `deliverable_globs`, `review`, `reports`.  
Schema file: `scout/schema/ticket_review_response.v1.json`.

---

## Definition of done

A developer can invoke **Semantic Scout for** any supported AN or PIC ticket, receive a traceable assessment of every acceptance criterion and expected artifact, see coverage and hygiene scores, fix identified gaps, and obtain a defensible **READY** result before opening a pull request — **without** maintaining ticket-specific checklists or scripts on the feature branch.
