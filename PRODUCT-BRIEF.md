# Semantic Scout MCP — product brief (copy template)

Use this block for Slack, Confluence, rollout decks, or Jira tooling pages. Same structure as other Insights MCP products.

---

**Semantic Scout MCP**

**Goal:** Give the team an on-demand way to check that Jira ticket work is complete on the feature branch before anyone opens a pull request.

**Description:** Semantic Scout is the ticket delivery-truth layer for Insights BI work. It reads the Jira summary, description, and comments, infers which artifacts belong to the ticket (dashboard, paginated report, semantic model), compares acceptance criteria to the git diff, scores Jira coverage and branch hygiene, lists missings, and surfaces likely review or bot feedback — so developers fix gaps in Cursor instead of after a PR bounce.

**Success looks like:** Any AN or PIC ticket can be reviewed on demand; every acceptance criterion gets a clear met or missing line tied to files; the review card shows scores and READY before the PR; setup is once per machine via **Setup Semantic Scout**; daily flow is **Semantic Scout for AN-XXXX** with no per-ticket checklists or one-off scripts in the repo.

**What we can achieve:** Standardized pre-PR review instead of scattered “are we good?” threads; faster intake when a new ticket starts; repeatable scope discipline (fewer stray `scripts/` or out-of-scope files on ticket branches); earlier catch of missing paginated companions, documentation, or parity items reviewers usually ask for.

**What we can use it for:** Pre-PR gate on every dashboard, paginated, or model change; regression check after DAX, RDL, filter, or documentation edits; new ticket kickoff to confirm scope and expected files; self-service review when reviewers are in sprint crunch.

**Setup (once):** In Cursor — **Setup Semantic Scout**

**Daily:** **Semantic Scout for AN-XXXX** (or PIC-XXXX) on your feature branch → fix missings → run again if needed → open PR.

**Team guide:** https://glofoxinc.github.io/semantic_scout/DOCUMENTATION.html

**Repo:** https://github.com/glofoxinc/semantic_scout
