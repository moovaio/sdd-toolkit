# Ticket system profile — UNSUPPORTED (manual setup required)

Your toolkit was installed with a ticket system that sdd-toolkit does **not** natively support,
so this is a **generic fallback** profile. `/implement` reads this file to know how to resolve and
fetch a ticket — out of the box it only knows the paste-in fallback below.

> **This file is yours to edit.** Unlike natively-supported systems, `sdd-toolkit update` will NOT
> overwrite it, so your changes are safe. Fill in the two sections below to wire up your system.
>
> To make it first-class for everyone instead, add `template/ai-specs/tickets/<system>/` to the
> sdd-toolkit repo (`ticket-system.md` + `ticket-template.md`) and re-run the installer with
> `--tickets=<system>`.

## Key format

- Define how a ticket is identified in your system (e.g. a numeric id `#1234`, a full URL, a slug).
- Describe the shape `/implement` should match in its arguments, and how to normalize it.
- If no valid key is present in the arguments, `/implement` must ask the user for it (AskUserQuestion)
  and NOT proceed without one.

<!-- TODO: replace with your system's key format. -->

## Reading a ticket

Pick ONE of these, document it here concretely, and delete the others so `/implement` can follow it:

- **MCP tool** — if your system has a Claude connector, name the tool(s) and how to load them
  (ToolSearch `select:...`), the auth flow (`/mcp`), and which fields to fetch.
- **REST API** — give the exact request `/implement` should run (e.g. a `curl` to your API with a
  token in an env var), and how the response maps to title / description / status / labels.
- **Paste-in only** — if there is no programmatic access, say so; `/implement` will ask the user to
  paste the ticket content.

<!-- TODO: replace with your system's fetch instructions. Until you do, only the fallback below works. -->

## Creating a ticket

Used by `/ticket` to create a new ticket after the user approves the draft.

- If you documented a programmatic create above (MCP tool or REST call), describe it here concretely —
  the request, auth, and how the drafted title/description map to your system's fields — and `/ticket`
  will follow it.
- If there's no automated create, leave this as-is: `/ticket` will present the finished ticket as clean
  Markdown (following `ticket-template.md`) for you to paste into your system by hand.

<!-- TODO (optional): document how to create a ticket programmatically in your system. -->

## Fallback

- If the ticket system is unreachable or these instructions are still unfilled, ask the user to paste
  the ticket content instead of guessing. This always works and is the current default.
