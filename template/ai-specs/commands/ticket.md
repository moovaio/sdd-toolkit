---
name: "Create a ticket from an idea"
description: From a plain-language idea, research the codebase, draft a ticket in the repo's template format, and — after approval — create it in the configured ticket system.
category: Workflow
tags: [workflow, ticket]
---

Turn a rough idea into a well-formed ticket, grounded in this codebase, and create it in the
configured ticket system. This command **drafts → stops for your review → iterates → creates**.
It pairs with `/implement`: the ticket this produces can be fed straight into `/implement <key>`.

**Input**: The argument after `/ticket` is a free-text description of what you want built or fixed
(e.g. `/ticket add a rate limit per application on the geocode endpoint`). If no idea is given,
use the **AskUserQuestion tool** to ask what the ticket should cover before doing anything else.

This command is **repo- and ticket-system agnostic**. It reads three sources of truth instead of
hardcoding specifics:
- **`ai-specs/ticket-template.md`** — the exact section structure the drafted ticket must follow.
- **`ai-specs/ticket-system.md`** — how to create a ticket (the "Creating a ticket" section: MCP tool
  / REST call, metadata, auth) for the installed system.
- **This repo's agent instructions** (`CLAUDE.md` / `AGENTS.md`) — authoring conventions: title
  format/prefix, description language, target project/board, issue type, labels. Follow them; do not
  assume conventions from other repos. If a needed convention isn't documented, **ask** the user
  (AskUserQuestion) and suggest they add it to `CLAUDE.md` so it's captured next time.

Creating a ticket is an **outward-facing action** — only do it after the user approves the draft.

---

## Step 1 — Clarify the idea (interactive)

- If no idea was given, ask what the ticket should cover (AskUserQuestion) before anything else.
- If the idea is thin or ambiguous, ask **1–3 focused clarifying questions** (AskUserQuestion) before
  drafting — e.g. scope boundaries, the observable behavior the acceptance criteria should target, or
  which area/module it touches. Don't over-ask: skip this when the idea is already concrete.

## Step 2 — Ground the idea in the codebase

- Read `CLAUDE.md` / `AGENTS.md` first (they document the architecture and conventions), then explore
  the specific modules the idea touches so the ticket is concrete and anchored to **real files and
  functions** — not generic. Prefer citing actual paths over hand-wavy descriptions.
- Note the repo's ticket-authoring conventions found there (title prefix, description language,
  project/board, issue type, labels). Hold anything still unknown for Step 4.

## Step 3 — Draft the ticket and STOP for review

- Draft the ticket **using `ai-specs/ticket-template.md` as the exact structure** — same sections, in
  order. Fill each section grounded in what you found in Step 2. Omit a section only if truly N/A
  (mark it `N/A` rather than deleting, matching the template's guidance).
- Apply the repo's authoring conventions (language, title format/prefix). The **title** should be
  concise (~3–8 words) and follow this repo's convention; if none is documented, ask.
- Keep it **basic-but-complete**: enough that a reader understands the what/why and the acceptance
  criteria are verifiable. It does not need to be exhaustive — it's a starting point to hand-edit.
- Present the drafted title + description to the user. **Do NOT create the ticket yet.** Iterate on the
  draft until the user approves — refining scope, criteria, fields, etc.

## Step 4 — Create the ticket

- Confirm the creation **metadata interactively** (AskUserQuestion) with sensible defaults discovered
  from the codebase / conventions / the ticket system — e.g. project or board, issue type, target
  sprint vs. backlog, labels. Don't hardcode values that vary; resolve or confirm them.
- Create by following the **"Creating a ticket" section of `ai-specs/ticket-system.md`** (the tool,
  request, auth flow, and metadata resolution live there — not here).
- **If that profile documents no programmatic create** (e.g. an unsupported/paste-in system), do not
  fail: present the finished ticket as clean Markdown (following the template) for the user to paste
  into their system by hand, or offer to save it to a file.
- Report the created ticket's key/id + URL, and **offer to continue with `/implement <key>`**.

**Guardrails**
- Creating the ticket is outward-facing — only after the user approves the draft (Step 3).
- Never invent code paths: if the idea is too vague to ground in the codebase, ask a clarifying
  question rather than writing a generic ticket.
- Follow this repo's conventions (title/language/project) from `CLAUDE.md` / `AGENTS.md`; ask when a
  convention is missing instead of guessing, and don't carry over another repo's conventions.
- Resolve system metadata dynamically (e.g. the active sprint) as the ticket-system profile describes
  — do not hard-code values that change.
