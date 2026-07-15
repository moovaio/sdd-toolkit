---
name: "Implement a ticket"
description: From a ticket key, create the branch, generate the OpenSpec artifacts, and — after approval — implement the code.
category: Workflow
tags: [workflow, ticket, openspec]
---

End-to-end implementation of a ticket. This command orchestrates the existing OpenSpec flow
(`/opsx:propose` → review → `/opsx:apply`) but starts from a ticket: it reads the ticket,
creates the branch following this repo's convention, generates the change artifacts, runs an
**independent `spec-reviewer` pass**, **stops for your review**, and only then writes code.

**Input**: The argument after `/implement` is the ticket key (e.g. `/implement MOOV-5147`).

This command is **repo- and ticket-system agnostic**. It reads two sources of truth instead of
hardcoding specifics:
- **`ai-specs/ticket-system.md`** — how to extract the ticket key and fetch the ticket (installed per `--tickets=<system>`).
- **This repo's agent instructions** (`CLAUDE.md` / `AGENTS.md`) — branch naming, commit/PR conventions,
  lint, and codebase conventions. Follow them; do not assume conventions from other repos.

This command confirms with the user at every irreversible step (branch name, before touching code).
Do NOT skip the confirmations.

---

## Step 0 — Resolve the ticket key

- Read `ai-specs/ticket-system.md` for the key format. Extract a matching key from `$ARGUMENTS` and normalize it.
- If no valid key is present, use the **AskUserQuestion tool** to ask for it. Do NOT proceed without a key.

## Step 1 — Read the ticket

- Follow the **fetch instructions in `ai-specs/ticket-system.md`** to read the ticket (MCP tool, auth flow,
  and any tenant resolution live there — not here).
- Show the user a short summary: key, title, type, status, and a 2–3 line digest of the description so they
  can confirm it's the right ticket.
- If the ticket is thin (no clear scope or acceptance criteria), note it and point the user to the ticket
  template at `ai-specs/ticket-template.md` — a better-structured description produces better artifacts.
  Proceed only with what the ticket provides; do not invent requirements.
- If the ticket system is unreachable, follow its fallback (ask the user to paste the ticket) rather than guessing.

## Step 2 — Pre-flight git state

- Fetch the repo's default branch (e.g. `git fetch origin <default-branch>`).
- Confirm the working tree is clean enough to branch. If there are uncommitted changes that would be carried over,
  warn the user and ask how to proceed (stash / continue / abort).
- **Branch first** — never implement directly on the default branch.

## Step 3 — Propose the branch name and CONFIRM

- Derive a kebab-case slug (~3–6 words) from the ticket summary. Build the branch name following **this repo's
  branch-naming convention** (see `CLAUDE.md` / `AGENTS.md`); it MUST include the ticket key.
- **Show the derived branch name and use the AskUserQuestion tool to confirm it** before creating anything.
  Get the name right up front: on most hosts, renaming a branch after a PR is open detaches or closes the PR.
  Let the user override the slug.
- Once confirmed, create it from the fresh default branch:
  ```bash
  git checkout -b <branch-name> origin/<default-branch>
  ```

## Step 4 — Generate OpenSpec artifacts (propose)

- Follow the **`openspec-propose` skill** / `/opsx:propose` flow, but use the **ticket content as the input
  description** instead of asking the user what to build.
- Use a change name consistent with the branch (a lower-case slug that includes the ticket key).
- Create the change and all artifacts required for apply (`proposal.md`, `design.md`, `tasks.md`) by following
  the `openspec` CLI exactly as `/opsx:propose` describes:
  `openspec new change` → `openspec status --json` → `openspec instructions <artifact> --json` per artifact.
- Ground the artifacts in the actual codebase: explore the relevant modules so the design and tasks match the
  repo's existing conventions and structure (see `CLAUDE.md` / `AGENTS.md`).

## Step 5 — Independent spec review, then STOP for approval (do NOT write code yet)

- **First, run the `spec-reviewer` subagent** (Agent tool, `subagent_type: "spec-reviewer"`),
  passing the change path `openspec/changes/<change-name>/` and the ticket key.
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
  change: implement tasks one by one, marking each `- [ ]` → `- [x]` as you go.
- Keep changes minimal and scoped per task. Pause and ask if a task is ambiguous or implementation reveals a
  design issue (suggest updating the artifacts rather than guessing).
- Respect this repo's project constraints from `CLAUDE.md` / `AGENTS.md` (lint/format commands, protected
  strings, routing/DB conventions, etc. — run the repo's lint before considering a task done where relevant).

## Step 7 — Wrap up

- Show final task progress.
- Do NOT commit or push unless the user asks. If/when they do, follow this repo's commit-message and PR
  conventions (language, format) from `CLAUDE.md` / `AGENTS.md`; lint before pushing.
- When all tasks are done, suggest `/opsx:archive` to archive the change.

**Guardrails**
- Confirm before every irreversible step (branch creation, first code change).
- Never write application code before the user approves the artifacts.
- If the ticket system is unreachable, ask the user to paste the ticket content instead of guessing.
- Reuse the existing `opsx` / `openspec-*` flows — do not reimplement their logic here.
