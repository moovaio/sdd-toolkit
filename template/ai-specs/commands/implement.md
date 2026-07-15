---
name: "Implement Jira ticket"
description: From a Jira ticket (MOOV-XXXX), create the branch, generate the OpenSpec artifacts, and — after approval — implement the code.
category: Workflow
tags: [workflow, jira, openspec, moova]
---

End-to-end implementation of a Jira ticket. This command orchestrates the existing
OpenSpec flow (`/opsx:propose` → review → `/opsx:apply`) but starts from a Jira ticket:
it reads the ticket, creates the branch with the team naming convention, generates the
change artifacts, runs an **independent `spec-reviewer` pass**, **stops for your review**,
and only then writes code.

**Input**: The argument after `/implement` is the Jira ticket key (e.g. `/implement MOOV-5147`).

This command confirms with the user at every irreversible step (branch name, before touching code).
Do NOT skip the confirmations.

---

## Step 0 — Resolve the ticket key

- The argument is `$ARGUMENTS`. Extract a key matching `MOOV-\d+` (case-insensitive, normalize to upper-case).
- If no valid key is present, use the **AskUserQuestion tool** to ask for the Jira ticket ID. Do NOT proceed without it.

## Step 1 — Read the Jira ticket

- The Atlassian/Jira MCP tools are deferred in fresh sessions. If `getJiraIssue` is not available, load it with
  **ToolSearch**: `select:mcp__claude_ai_Atlassian_Rovo__getJiraIssue,mcp__claude_ai_Atlassian_Rovo__getAccessibleAtlassianResources`.
- If the MCP is not authenticated (the call fails asking for auth), stop and tell the user to run `/mcp` and select
  **"claude.ai Atlassian Rovo"**, then re-run `/implement`.
- Resolve the `cloudId` dynamically via `getAccessibleAtlassianResources` and pick the
  resource whose `url` is `https://moova1.atlassian.net` (Moova's site is `moova1`). Prefer
  this over any hardcoded value — it stays correct if the tenant ever changes.
  Only if that call fails, fall back to the known `moova1` cloudId
  `59e666bf-d9f2-4276-892e-4890b9daeb13` (verified 2026-07 against `getAccessibleAtlassianResources`).
- Fetch the issue with `getJiraIssue` (`responseContentFormat: "markdown"`, fields:
  `summary`, `description`, `status`, `issuetype`, `labels`, `comment`).
- Show the user a short summary: key, title, type, status, and a 2–3 line digest of the description so they
  can confirm it's the right ticket.
- If the ticket is thin (no clear scope or acceptance criteria), note it and point the user to the ticket
  template at `ai-specs/ticket-template.md` — a better-structured description produces better artifacts.
  Proceed only with what the ticket provides; do not invent requirements.

## Step 2 — Pre-flight git state

- Run `git fetch origin master` (or the repo's default branch).
- Confirm the working tree is clean enough to branch. If there are uncommitted changes that would be carried over,
  warn the user and ask how to proceed (stash / continue / abort).
- Per CLAUDE.md: **branch first** — never implement directly on the default branch.

## Step 3 — Propose the branch name and CONFIRM

- Derive a kebab-case slug (~3–6 words) from the ticket summary. Branch name MUST be
  `MOOV-<number>-<kebab-slug>` (CLAUDE.md: branch names must start with the Jira ticket ID).
- **Show the derived branch name and use the AskUserQuestion tool to confirm it** before creating anything.
  This is intentional and required: renaming a branch on GitHub after a PR is open closes the PR
  (CLAUDE.md), so the name must be right up front. Let the user override the slug.
- Once confirmed, create it from fresh master:
  ```bash
  git checkout -b MOOV-<number>-<kebab-slug> origin/master
  ```

## Step 4 — Generate OpenSpec artifacts (propose)

- Follow the **`openspec-propose` skill** / `/opsx:propose` flow, but use the **ticket content as the input
  description** instead of asking the user what to build.
- Use a change name consistent with the branch: `moov-<number>-<kebab-slug>` (lower-case).
- Create the change and all artifacts required for apply (`proposal.md`, `design.md`, `tasks.md`) by following
  the `openspec` CLI exactly as `/opsx:propose` describes:
  `openspec new change` → `openspec status --json` → `openspec instructions <artifact> --json` per artifact.
- Ground the artifacts in the actual codebase: explore the relevant modules under `api/` and `infrastructure/`
  so the design and tasks match existing conventions (Controller → FormRequest → Service → Repository,
  module ServiceProviders, Json transformers, etc. — see CLAUDE.md).

## Step 5 — Independent spec review, then STOP for approval (do NOT write code yet)

- **First, run the `spec-reviewer` subagent** (Agent tool, `subagent_type: "spec-reviewer"`),
  passing the change path `openspec/changes/moov-<number>-<kebab-slug>/` and the ticket key.
  It reviews the artifacts against the real codebase in a fresh, independent context and
  returns a prioritized findings report with a verdict. Running it here — before human
  approval — is the point: it catches scope gaps, convention mismatches, and invariant
  risks that the authoring context is biased to miss.
- Present a concise summary of the generated artifacts (what changes, the design approach,
  and the task list) **together with the spec-reviewer's report**, so the user approves
  with that review in hand.
- If the review surfaces `APPROVE-WITH-CHANGES` or `REJECT`, address the findings (update
  the artifacts) before asking for approval, or explain why a finding is being deferred.
- **Explicitly wait for the user's approval.** Do not modify any application code until the user agrees.
- If the user requests changes to the artifacts, update them and re-present. Iterate until they approve.

## Step 6 — Implement (apply)

- Only after explicit approval, follow the **`openspec-apply-change` skill** / `/opsx:apply` flow for the
  change `moov-<number>-<kebab-slug>`: implement tasks one by one, marking each `- [ ]` → `- [x]` as you go.
- Keep changes minimal and scoped per task. Pause and ask if a task is ambiguous or implementation reveals a
  design issue (suggest updating the artifacts rather than guessing).
- Respect project constraints from CLAUDE.md: PSR-2 (run `vendor/bin/phpcs --standard=phpcs.xml` before
  considering a task done where relevant); do not change CloudWatch alert log strings; keep route ID patterns
  non-numeric; pick DB connections explicitly for cross-DB work.

## Step 7 — Wrap up

- Show final task progress.
- Do NOT commit or push unless the user asks. If/when they do: commit messages follow the `git log` style
  (`MOOV-<number>. <Description>`); PRs and review comments are written in **Spanish**; lint before pushing.
- When all tasks are done, suggest `/opsx:archive` to archive the change.

**Guardrails**
- Confirm before every irreversible step (branch creation, first code change).
- Never write application code before the user approves the artifacts.
- If Jira is unreachable, ask the user to paste the ticket content instead of guessing.
- Reuse the existing `opsx` / `openspec-*` flows — do not reimplement their logic here.
