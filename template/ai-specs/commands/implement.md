---
name: "Implement a ticket"
description: From a ticket key, create the branch, generate the OpenSpec artifacts, and — after approval — implement the code.
category: Workflow
tags: [workflow, ticket, openspec]
---

End-to-end implementation of a ticket. This command orchestrates the existing OpenSpec flow
(`/opsx:propose` → review → `/opsx:apply`) but starts from a ticket: it reads the ticket,
creates the branch following this repo's convention, generates the change artifacts, runs an
**independent `spec-reviewer` pass**, **stops for your review**, writes code, then **stops again**
before anything becomes a PR — **suggesting** (not running) an independent `code-reviewer` pass
on the diff. The plan review runs by default and is skipped only for small mechanical changes;
the code review is always yours to ask for.

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

- **First check whether this ticket already has a change** under `openspec/changes/` (its name
  includes the ticket key). If it does and its artifacts are complete, this is a resumed cycle:
  confirm with the user that they already approved these artifacts, then **skip to Step 6**. Do
  not regenerate artifacts or re-run the review that was already paid for.
- Follow the **`openspec-propose` skill** / `/opsx:propose` flow, but use the **ticket content as the input
  description** instead of asking the user what to build.
- Use a change name consistent with the branch (a lower-case slug that includes the ticket key).
- Create the change and all artifacts required for apply (`proposal.md`, `design.md`, `tasks.md`) by following
  the `openspec` CLI exactly as `/opsx:propose` describes:
  `openspec new change` → `openspec status --json` → `openspec instructions <artifact> --json` per artifact.
- Ground the artifacts in the actual codebase: explore the relevant modules so the design and tasks match the
  repo's existing conventions and structure (see `CLAUDE.md` / `AGENTS.md`).

## Step 5 — Independent spec review, then STOP for approval (do NOT write code yet)

- **Decide whether to run the `spec-reviewer` subagent** (Agent tool, `subagent_type: "spec-reviewer"`),
  passing the change path `openspec/changes/<change-name>/` and the ticket key. It reviews the
  artifacts against the real codebase in a fresh, independent context and returns a prioritized
  findings report with a verdict. Running it *before* human approval is the point: it catches
  scope gaps, convention mismatches, and invariant risks the authoring context is biased to miss.
  - **Default to running it.** An independent review pass costs real time and tokens, so it is
    not unconditional — but the bar for skipping is high, and when in doubt, run it.
  - **Run it** whenever the change is non-trivial (several tasks, more than a couple of files)
    **or** touches load-bearing surface: authentication, authorization, application bootstrap or
    service providers, public endpoints, migrations, money, queues, or anything this repo's
    `CLAUDE.md` / `AGENTS.md` marks as an invariant.
  - **Offer to skip it** only when the change is *both* small *and* mechanical — a handful of
    tasks, no sensitive surface, no new behavior (a rename, a config value, a copy change).
    Say what you're skipping and why, and let the user ask for it anyway.
- Present a concise summary of the generated artifacts (what changes, the design approach,
  and the task list) **together with the spec-reviewer's report** when one was run, so the
  user approves with that review in hand.
- If the review surfaces `APPROVE-WITH-CHANGES` or `REJECT`, address the findings (update
  the artifacts) before asking for approval, or explain why a finding is being deferred.
- **Explicitly wait for the user's approval.** Do not modify any application code until the user agrees.
- If the user requests changes to the artifacts, update them and re-present. Iterate until they approve.
- **Once they approve, suggest continuing in a fresh session** before you start Step 6:
  > The approved artifacts in `openspec/changes/<change-name>/` are the complete handoff —
  > `/opsx:apply` needs nothing from this conversation. Starting a new session here drops the
  > ticket fetch, the codebase exploration and the review report out of the context that every
  > implementation turn re-reads, which is the single largest cost in this cycle.

  Tell them the exact way to resume (`/opsx:apply <change-name>`, or `/implement <KEY>` which
  will find the existing change). **It is a suggestion, not a gate** — if they'd rather continue
  here, continue with Step 6 immediately and don't raise it again.

## Step 6 — Implement (apply)

- Only after explicit approval, follow the **`openspec-apply-change` skill** / `/opsx:apply` flow for the
  change: implement tasks one by one, marking each `- [ ]` → `- [x]` as you go.
- Keep changes minimal and scoped per task. Pause and ask if a task is ambiguous or implementation reveals a
  design issue (suggest updating the artifacts rather than guessing).
- Respect this repo's project constraints from `CLAUDE.md` / `AGENTS.md` (lint/format commands, protected
  strings, routing/DB conventions, etc. — run the repo's lint before considering a task done where relevant).

## Step 7 — STOP for approval, and SUGGEST an independent code review (before any PR)

- Present a concise summary of the finished implementation: what changed, which tasks are done,
  and anything worth a closer look.
- **Suggest — do not run — an independent code review.** Offer the `code-reviewer` subagent
  (Agent tool, `subagent_type: "code-reviewer"`) as the recommended next step: it reviews the
  **implementation diff** against the approved artifacts and the real codebase in a fresh,
  independent context, and its distinctive job is conformance — did the code do what was approved
  in Step 5? Name it explicitly so the user can ask for it in one word. **Only run it if the user
  asks.** Do not spend a review pass they didn't request.
- If the change touches security-sensitive surface (auth, public endpoints, data handling,
  query building, secrets), **also suggest `/security-review`** on the diff — a dedicated pass
  tuned for vulnerabilities, complementary to the `code-reviewer`. Same rule: offer it, don't run it.
- If the user does request a review and it surfaces `APPROVE-WITH-CHANGES` or `REJECT`, fix the
  findings (following the same skills/conventions as Step 6) before asking for approval, or
  explain why a finding is being deferred. Re-run the reviewer after non-trivial fixes.
- **Explicitly wait for the user's approval.** Do not commit, push, or open a PR until the user
  agrees — with or without a code review having been run. Skipping the review is the user's call.
- If the implementation was long (many tasks, a lot of exploration, a test/lint loop), **mention
  that a review or the PR can run in a fresh session**: the diff on the branch and the approved
  artifacts are all a reviewer needs, and by this point every turn is re-reading the whole
  implementation history. Same rule as Step 5 — suggest once, don't insist, don't block.

## Step 8 — Wrap up

- Show final task progress.
- Do NOT commit or push unless the user asks. If/when they do, follow this repo's commit-message and PR
  conventions (language, format) from `CLAUDE.md` / `AGENTS.md`; lint before pushing.
- When all tasks are done, suggest `/opsx:archive` to archive the change.

**Guardrails**
- Confirm before every irreversible step (branch creation, first code change).
- Never write application code before the user approves the artifacts (Step 5).
- The fresh-session suggestions (Steps 5 and 7) are suggestions. Never refuse to continue in the
  current session, and never raise the same one twice.
- Never commit, push, or open a PR before the user approves the implementation (Step 7).
- Never launch the `code-reviewer` (or `/security-review`) on your own — suggest it and wait to be asked.
- If the ticket system is unreachable, ask the user to paste the ticket content instead of guessing.
- Reuse the existing `opsx` / `openspec-*` flows — do not reimplement their logic here.
