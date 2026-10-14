---
name: "Daily summary"
description: Summarize what you worked on, what reached dev and what reached production on a given day, from git history and the ticket system — ready to say at the daily.
category: Analysis
tags: [analysis, daily, git, tickets]
---

Rebuild what you did on a given day — typically the last working day, when it's Monday and
Friday is a blur — from the two places it actually left a trace: **git history** and the
**ticket system**. The output is a short summary to read out at the daily, not a changelog.

**Input**: optionally a date, `YYYY-MM-DD` (`/daily 2026-09-25`). With no argument, use the
**previous working day** relative to today (Monday → the previous Friday; Saturday/Sunday →
Friday; otherwise yesterday). The window is that whole local day: `D 00:00` to `D+1 00:00`.

This command is **repo- and ticket-system agnostic**. It reads:
- **This repo's agent instructions** (`CLAUDE.md` / `AGENTS.md`) — which branch is the dev
  environment and which is production (don't assume `dev` / `master`), and which other repos
  the day's work may live in.
- **`ai-specs/ticket-system.md`** — the ticket key format and the "Listing recent activity"
  section (how to find your tickets touched in a date window).

It is **read-only**: it never pushes, comments, transitions tickets, or posts anywhere.

---

## Step 1 — Resolve the date and who "you" are

- Parse the date from `$ARGUMENTS`; if it's malformed, ask (AskUserQuestion). Compute `D+1`.
- Identity for git: `git config user.name` and `git config user.email`. Match on **both**
  (repeat `--author`, which git ORs) — people often commit with a personal email on one machine
  and a work email on another.

## Step 2 — Resolve the repos to read

Work rarely stays in one repo, so the day is read from **this repo plus the ones listed** in a
"Daily repos" note of the agent instructions — the repo's `CLAUDE.md` / `AGENTS.md`, or a personal
one already in context (`CLAUDE.local.md`, `~/.claude/CLAUDE.md`), since which repos *you* touch
is often personal rather than the team's:

```markdown
## Daily repos
- `../api_go`
- `../web-app`
```

- Paths are relative to this repo's root (absolute and `~/` paths are fine too).
- An entry that doesn't exist on this machine, or isn't a git repo, is **skipped** and named in
  the caveats line — a teammate who never cloned it should get a summary, not an error.
- Without the note, read only this repo.

Steps 3 and 4 run **for each repo**, with that repo's own identity, branches and remote.

## Step 3 — Resolve the environment branches (per repo)

- **Configured**: if the repo's `CLAUDE.md` / `AGENTS.md` has an "Environment branches" note,
  use it. The shape to read (and to write, below):
  ```markdown
  ## Environment branches
  - dev: `dev`
  - production: `master`
  ```
- **Default**: otherwise detect from the remote (`git branch -r`): dev is the first of `dev`,
  `develop`, `development`, `staging` that exists; production is the first of `master`, `main`,
  `production`. If none or several plausible candidates exist, ask (AskUserQuestion).
- **If you had to detect or ask, offer once to persist it** in that shape, so the next run reads
  it instead of guessing. Only write it if the user agrees — and only in **this** repo; for a
  listed repo, just mention what was detected (writing there would leave a stray change in a
  repo the user didn't open).

## Step 4 — Read git history (per repo)

Run every command with `git -C <repo>`. Take the identity from **that** repo's `git config` and
add this repo's too (repeat `--author`), since the same person may have configured them
differently. Run `git fetch --quiet origin` first so remote branches are current (if it fails —
offline, no auth — continue with the local refs and say which repo may be stale).

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

## Step 5 — Read the ticket system

Run this **once**, not per repo — the query is by person and date, not by repo. Follow the
**"Listing recent activity" section of `ai-specs/ticket-system.md`** for the window `D`..`D+1`: tickets you created, and tickets you moved or that are assigned to you and changed.

- If the profile has no such section, or the system is unreachable, **skip this step** and say
  the summary is from git only — don't fail and don't ask the user to paste tickets.
- Use the ticket titles to name the git groups from Step 4. For a key seen in git but absent
  from the results, fetch it only if there are a few (≤ 5); otherwise show the bare key.
- A ticket with activity but **no commits in any repo read** may simply be work in a repo that
  isn't listed. List it under its own line (see Step 6) and, if there's no "Daily repos" note
  yet, offer once to add one — ask which repo it was, and write the note to this repo's
  agent instructions only if the user agrees.

## Step 6 — Write the summary

Write it in the language the user is writing in. Keep it short enough to say out loud — one line
per item, ticket key first, plain language, no hashes. Omit empty sections; if the whole day is
empty, say so and suggest another date (e.g. it was a holiday, or the work is in a repo not
listed under "Daily repos").

When more than one repo contributed, tag each item with its repo in parentheses after the key,
so the listener knows which service it was; with a single repo, leave the tag out. The same
ticket in two repos is one line with both tags.

```
**<weekday> <D>**

Trabajé en:
- MOOV-5147 (core-api) — rate limit por aplicación en geocode (en review)
- MOOV-5160 (api_go) — investigué el timeout de la integración X, sin cambios todavía

Pasó a dev:
- MOOV-5147 (core-api) — rate limit por aplicación

Pasó a producción:
- MOOV-5102 (core-api) — fix del cálculo de ETA

Tickets creados:
- MOOV-5171 — agregar métricas al endpoint de tracking

Con movimiento en el ticket system, sin commits en los repos leídos:
- MOOV-5180 — actualizar dependencias del servicio de ruteo
```

After the summary, one line of caveats **only if they apply**: a fetch failed, a listed repo was
missing, tickets were skipped, or the date is today (so the day isn't over).

**Guardrails**
- Read-only. Never push, merge, comment on or transition a ticket, or post the summary anywhere.
- Only the repos resolved in Step 2 — if the user expected work from another one, point them
  to the "Daily repos" note rather than searching the disk for it.
- Never write to a listed repo; the only file this command may write is this repo's agent
  instructions, and only after the user agrees.
- Don't pad the summary with other people's work; the dev/production lists are what *you* shipped.
- Don't invent what a commit did — if a group is unclear from its messages and diff stat, name
  the ticket/branch and leave it at that.
