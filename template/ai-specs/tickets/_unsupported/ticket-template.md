# Ticket template (for use with `/implement`)

Paste this skeleton into your ticket's description. It is designed as the "negative"
of what the OpenSpec flow asks for: each section feeds directly into an artifact that
`/implement` generates (see `.claude/commands/implement.md`), so the `proposal.md` /
`design.md` / `specs/` come out with less back-and-forth.

This is a **system-neutral** template shipped because your ticket system isn't natively
supported. Feel free to tailor it to your tool's fields; `sdd-toolkit update` won't overwrite it.

The more complete the sections, the better the artifacts. For the ones that don't apply,
leave them as "N/A" instead of deleting them (it makes explicit that they were considered).

---

## Context / Problem
<!-- 1-3 sentences: what problem it solves and why now. Feeds the "Why" of the proposal. -->

## What is wanted (scope)
<!-- Concrete changes as bullets: new endpoints, modifications, removals.
     Mark anything that breaks compatibility with **BREAKING**. Feeds "What Changes". -->
-

## Acceptance criteria
<!-- Verifiable conditions. Each one becomes a WHEN/THEN Scenario in the spec.
     Phrase them in terms of observable behavior, not implementation. -->
- [ ]
- [ ]

## Out of scope (Non-goals)
<!-- What explicitly does NOT belong in this ticket. Prevents scope creep in the artifacts. -->
-

## Technical notes / integrations
<!-- Example endpoints and payloads, affected platforms/modules, DB connections,
     and concrete test data (e.g. "use order 1215"). Feeds the design. -->
-

## Dependencies / risks
<!-- Related tickets, external services, config flags, and known risks. -->
-

---

### Writing tips
- One ticket = one objective. If there are several independent objectives, split it.
- Acceptance criteria are the most valuable part for `/implement`: they translate almost 1:1
  into the scenarios in `spec.md`.
- If the ticket touches repo conventions (routes, queues, scheduled jobs, DB connections),
  mention it in "Technical notes" — the command anchors the artifacts to `CLAUDE.md`.
