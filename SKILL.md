---
name: semantic-scout
description: "Semantic Scout: before raising a PR, rate Jira requirements vs the branch, list missings, and suggest ahead (bot comments, documentation, dashboard vs paginated companions). Use when the user says Semantic Scout, rate this ticket, before PR, bot comments ahead, scope preflight, or Setup Semantic Scout."
metadata:
  team: CC171 Insights & Reporting / Glofox Analytics
  schema_version: "3.0-scout"
  surfaces: [ide, cli]
---

# Semantic Scout

Product skill. Load this first. Then load `bi-insights-pr-review` (BI gates) and `semantic-pr-review` (18-category JSON) as needed.

**Job:** Before the PR exists, analyse the Jira ticket and the current branch, give **ratings**, list **missings**, and give **ahead suggestions**. Do not tell the user to raise the PR until they pick **B**.

## When to run

| User says | Do this |
|-----------|---------|
| Semantic Scout / rate this ticket / before PR | Full Scout card on **local branch** |
| Scope preflight for AN-XXXX | Same, after Jira fetch + git diff |
| Setup Semantic Scout | Load `setup-semantic-scout` instead |

## Hard rules

1. **Honesty.** Never mark a requirement `met` without a file path you actually read. Use `unverified` if you have not seen the evidence.
2. **Ratings always.** Every Scout run ends with the **SCOUT RATING CARD**. No card = incomplete run.
3. **Missings always.** If none, write `NONE`. Do not skip the section.
4. **Suggestions always.** Include bot-ahead plus companion intelligence (docs / dashboard / paginated / model). If none, write `NONE`.
5. **ASCII.** No emoji in the card.
6. **No PR until B.** After the card, ask A / B / C. Raise PR only on **B**.

## Procedure

### 1. Jira (user gives the ticket key only)

The user provides **AN-XXXX** or **PIC-XXXX**. They do not need to name the GitHub repo or the branch.

Fetch the ticket (Atlassian MCP). Use summary, description, acceptance criteria, **all comments** (QA comments are requirements).

One-sentence deliverable. Numbered AC list. If AC cannot be listed, STOP and ask.

### 2. Detect repo, then detect branch (mandatory)

Use shipped routing: `skill/rules/GLOFOX-JIRA-ROUTING.md` + `skill/data/glofox-repo-jira-exemplars.json` + `python skill/lib/jira_repo_router.py <KEY> --summary "<summary>"`.

**Repo (from ticket project + title, not from the user):**

| Jira | Signal | Repo |
|------|--------|------|
| AN-XXXX | Standard report names, no client brand | `glofoxinc/gf-insights-fitnessbi` |
| AN or PIC | Fabric, lakehouse, gold layer, notebook | `glofoxinc/gf-fabric-fitnessbi` |
| PIC-XXXX | Client in title (Jetts, Lift, ...) | matching `glofoxinc/abc-customize-*` |
| Any | `github.com/glofoxinc/...` in the ticket | that repo wins |

If confidence is **low**, state the guess and ask before deep review.

**Branch (from the ticket key, on that repo):**

1. Prefer local clone if the user has it; else GitHub MCP list branches.
2. Match `feature/<KEY>-*`, then `<KEY>-*`, then current checked-out branch if it contains the key.
3. Diff base: custom repos → `origin/main`. `gf-insights-fitnessbi` feature work → `origin/main`. Promotion PR → `origin/Standard_dev` only if the user said so.

Print this before ratings:

```
JIRA ROUTING:
Ticket: <KEY> — <one-line summary>
GitHub: glofoxinc/<repo> (confidence: high|medium|low)
Branch: <detected>   Base: origin/main | origin/Standard_dev
```

If no branch matches the key, STOP and ask. Do not invent a branch.

Then:

```
git diff origin/<base>...HEAD --name-status
git diff origin/<base>...HEAD
```

Classify every path: dashboard (`*.Report`, `report.json`, `visual.json`), paginated (`.rdl`), semantic model (`.tmdl`, `.SemanticModel`), documentation (Measures and Definitions, doc page in RDL), scripts/docs/.github (usually out of scope).

### 3. Map each AC to the diff

| Status | Meaning |
|--------|---------|
| met | You saw the change in the file |
| partial | Related change exists, AC not fully covered |
| missing | Ticket asks for it; branch does not have it |
| unverified | Ticket asks for it; you have not opened the file |
| extra | In the branch; not in the ticket (scope creep) |

### 4. Rate (do the math in chat)

**Jira requirement rating (0-100)**  
`(met * 100 + partial * 50) / count(AC excluding extra)`.  
If any AC is `unverified`, cap at **79** and say what to open.  
If any **must-have** AC is `missing`, cap at **49**.

**Branch rating (0-100)** start at 100, then subtract:

| Signal | Subtract |
|--------|----------|
| Path not in Jira (scripts/, extra .rdl, .github/, random docs) | 20 each class |
| Protected `report.json` toggle without ticket (`rowSubtotals`, `isInvertedSelectionMode`, `visualType`, `projections`) | 15 |
| Dashboard changed, companion paginated in ticket not updated | 15 |
| Paginated changed, companion dashboard in ticket not updated | 15 |
| KPI/filter/label change with no documentation page / Measures and Definitions | 10 |
| Date / filter / currency mismatch risk (dashboard vs .rdl) | 15 |
| Conflict markers or foreign ticket IDs in commits | 25 |

Floor at 0.

**Combined (before PR):** round `0.5 * jira + 0.5 * branch`.  
**Ready for PR:** YES only if combined >= 80, no `missing` must-have AC, no FIX_FIRST blockers, no unverified must-haves.

Also run `python skill/lib/before_pr_validation.py` (or `skill/scripts/before-pr-validation.ps1`) on changed paths. Merge its verdict into the card.

### 5. Intelligence — ahead suggestions (required)

Do not wait for the user to remember companions. **If the branch has X, suggest Y:**

| Branch contains | Suggest (if not already in the diff and the ticket is about that report) |
|-----------------|------------------------------------------------------------------------|
| Dashboard (`report.json`, `.Report`) | Matching paginated `.rdl` for the same report (dates, filters, currency, KPIs). Documentation / Measures and Definitions if KPI, filter, or label changed. Audit protected visual properties. Location slicer still select-all if that is production. |
| Paginated (`.rdl`) | Matching dashboard page. Date default MTD through yesterday. Date guard `@StartDate <= @EndDate`. NoRowsMessage, ErrorBanner. Doc-page column order matches the data page. |
| Both dashboard and paginated | Parity: date window, end-date guard, every new filter, currency by location (never hard-coded USD), same KPI logic. |
| Semantic model (`.tmdl`) | Report visuals still bind (`queryRef`). Unused objects: point user to **Semantic Forge** analyse -> Word plan -> confirm. Do not drop columns the report still uses. |
| KPI / measure / filter in Jira | Documentation page text in business language (purpose, when to use, field meaning). |
| Join Type / Location / date ticket | Dashboard slicer **and** every companion `.rdl` parameter in the same sprint. |
| New Members Details | JoinType must not include Continuing. |
| Fix-only ticket + new `.rdl` | STOP — new report needs its own Jira. |

Bot ahead: run `bot_preflight_advisor.py` on the same paths. List likely Cursor/Circuit comments and the fix. That is a **suggestion**, not a claim the bot already posted.

### 6. Emit this card (verbatim structure)

```
============================================================
SEMANTIC SCOUT — BEFORE RAISING PR
============================================================
Ticket: AN-XXXX — <one-line summary>
Branch: <name>  Base: origin/main  Repo: glofoxinc/<repo>

JIRA REQUIREMENT RATING:  <n>/100
BRANCH RATING:            <n>/100
COMBINED (BEFORE PR):     <n>/100   READY: YES | NO

REQUIREMENTS
  [met|partial|missing|unverified]  <AC 1>  —  <path or why>
  ...

MISSINGS
  - <what the ticket needs that the branch does not have>
  NONE

AHEAD SUGGESTIONS
  - Docs: <Measures and Definitions / RDL doc page / NONE>
  - Dashboard: <companion page or protected-prop audit / NONE>
  - Paginated: <companion .rdl or date/filter/currency / NONE>
  - Model: <tmdl / Forge / NONE>
  - Bot ahead: <likely comment -> suggested fix>
  - Other: <parity, JoinType, currency, scope creep>

VERDICT: CLEAR | CAUTION | FIX_FIRST
============================================================

What do you want to do next?
  A) FIX FIRST — apply the suggestions, then re-rate
  B) RAISE PR — I accept remaining risk
  C) RE-CHECK — I will edit locally first

Reply A, B, or C. I will not tell you to open the PR until you choose B.
```

If READY is NO, the next sentence must name the smallest set of fixes that would raise it to YES.

### 7. After the card

If the user wants the 18-category JSON, emit it **after** the card (see `semantic-pr-review`). Never skip the card to emit JSON only.

## CLI helpers (same clone)

```
python skill/lib/before_pr_validation.py --paths-file paths.txt --diff-file diff.txt
python skill/lib/companion_suggestions.py --paths-file paths.txt
python skill/lib/bot_preflight_advisor.py --paths-file paths.txt --diff-file diff.txt
```
