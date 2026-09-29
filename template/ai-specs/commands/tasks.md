---
name: "Daily summary"
description: Summarize what you worked on, what reached dev and what reached production on a given day, from git history and the ticket system — ready to say at the daily.
category: Analysis
tags: [analysis, daily, git, tickets]
---

Rebuild what you did on a given day — typically the last working day, when it's Monday and
Friday is a blur — from the two places it actually left a trace: **git history** and the
**ticket system**. The output is a short summary to read out at the daily, not a changelog.

**Input**: optionally a date, `YYYY-MM-DD` (`/tasks 2026-09-25`). With no argument, use the
**previous working day** relative to today (Monday → the previous Friday; Saturday/Sunday →
Friday; otherwise yesterday). The window is that whole local day: `D 00:00` to `D+1 00:00`.

This command is **repo- and ticket-system agnostic**. It reads:
- **This repo's agent instructions** (`CLAUDE.md` / `AGENTS.md`) — which branch is the dev
  environment and which is production. Don't assume `dev` / `master`.
- **`ai-specs/ticket-system.md`** — the ticket key format and the "Listing recent activity"
  section (how to find your tickets touched in a date window).

It is **read-only**: it never pushes, comments, transitions tickets, or posts anywhere.

---

## Step 1 — Resolve the date and who "you" are

- Parse the date from `$ARGUMENTS`; if it's malformed, ask (AskUserQuestion). Compute `D+1`.
- Identity for git: `git config user.name` and `git config user.email`. Match on **both**
  (repeat `--author`, which git ORs) — people often commit with a personal email on one machine
  and a work email on another.

## Step 2 — Resolve the environment branches

- **Configured**: if `CLAUDE.md` / `AGENTS.md` has an "Environment branches" note, use it. The
  shape to read (and to write, below):
  ```markdown
  ## Environment branches
  - dev: `dev`
  - production: `master`
  ```
- **Default**: otherwise detect from the remote (`git branch -r`): dev is the first of `dev`,
  `develop`, `development`, `staging` that exists; production is the first of `master`, `main`,
  `production`. If none or several plausible candidates exist, ask (AskUserQuestion).
- **If you had to detect or ask, offer once to persist it** in that shape, so the next run reads
  it instead of guessing. Only write it if the user agrees.

## Step 3 — Read git history

Run `git fetch --quiet origin` first so remote branches are current (if it fails — offline, no
auth — continue with the local refs and say the summary may be stale).

```bash
SINCE="<D> 00:00"; UNTIL="<D+1> 00:00"
ME=(--author="<user.name>" --author="<user.email>")

# What you worked on — every branch, your commits, with the ref each was reached from
git log --all --source --no-merges "${ME[@]}" --since="$SINCE" --until="$UNTIL" \
  --format='%h%x09%S%x09%s'

# What landed on dev / production that day — the branch's own timeline, one row per merge or push
git log origin/<dev>  --first-parent --since="$SINCE" --until="$UNTIL" --format='%h%x09%an%x09%s'
git log origin/<prod> --first-parent --since="$SINCE" --until="$UNTIL" --format='%h%x09%an%x09%s'
```

- **Worked on**: group the commits by ticket key (from the branch name or the message, using
  the "Key format" in `ai-specs/ticket-system.md`), falling back to the branch name. Summarize
  each group in one line of what changed — do not list commit messages.
- **Reached dev / production**: keep only the entries that are yours — you authored the commit
  (squash merge or direct push), or it's a merge whose merged side contains your commits
  (`git log <sha>^1..<sha>^2 "${ME[@]}" --oneline` is non-empty). Name each by its ticket/feature,
  not by the merge message.
- Promotions dev → production often arrive as one big merge; list the tickets it carried that
  are yours, not the merge itself.

## Step 4 — Read the ticket system

Follow the **"Listing recent activity" section of `ai-specs/ticket-system.md`** for the window
`D`..`D+1`: tickets you created, and tickets you moved or that are assigned to you and changed.

- If the profile has no such section, or the system is unreachable, **skip this step** and say
  the summary is from git only — don't fail and don't ask the user to paste tickets.
- Use the ticket titles to name the git groups from Step 3. For a key seen in git but absent
  from the results, fetch it only if there are a few (≤ 5); otherwise show the bare key.

## Step 5 — Write the summary

Write it in the language the user is writing in. Keep it short enough to say out loud — one line
per item, ticket key first, plain language, no hashes. Omit empty sections; if the whole day is
empty, say so and suggest another date (e.g. it was a holiday, or the work is in another repo).

```
**<weekday> <D>**

Trabajé en:
- MOOV-5147 — rate limit por aplicación en geocode (en review)
- MOOV-5160 — investigué el timeout de la integración X, sin cambios todavía

Pasó a dev:
- MOOV-5147 — rate limit por aplicación

Pasó a producción:
- MOOV-5102 — fix del cálculo de ETA

Tickets creados:
- MOOV-5171 — agregar métricas al endpoint de tracking
```

After the summary, one line of caveats **only if they apply**: the fetch failed, tickets were
skipped, or the date is today (so the day isn't over).

**Guardrails**
- Read-only. Never push, merge, comment on or transition a ticket, or post the summary anywhere.
- This repo only — say so if the user seems to expect work from other repos.
- Don't pad the summary with other people's work; the dev/production lists are what *you* shipped.
- Don't invent what a commit did — if a group is unclear from its messages and diff stat, name
  the ticket/branch and leave it at that.
