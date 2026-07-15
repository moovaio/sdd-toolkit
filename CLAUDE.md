# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **not an application** — it's a **distribution/installer** for Moova's Spec-Driven Development (SDD) assets. It ships a set of Claude agents, skills, and slash commands for the OpenSpec workflow, and installs them into *other* repos so every team shares one setup and can pull updates centrally.

The assets under `template/` are the payload; they run inside *consumer* repos, not here. Do not try to "run the workflow" in this repo — there is no OpenSpec project, no ticket integration, and no app to build here.

## Commands

There is no build, test, or lint tooling — `package.json` has no dependencies and no scripts. The CLI is a single zero-dependency Node file (`bin/init.js`).

Exercise it against a throwaway target directory:

```bash
node bin/init.js init /tmp/test-repo                          # scaffold into a fresh repo
node bin/init.js init /tmp/test-repo --agents=claude --tickets=jira
node bin/init.js update /tmp/test-repo --dry-run              # preview an update
node bin/init.js update /tmp/test-repo                        # apply an update
node bin/init.js help
```

`--dry-run` on `update` is the fastest way to verify changes to the copy/symlink logic without mutating anything.

## Architecture

Two moving parts: the installer (`bin/init.js`) and the asset payload (`template/`).

### The three asset classes (this is the core model)

`bin/init.js` treats template files in three distinct ways — understanding which class a file belongs to is essential before editing:

1. **Managed** (`template/ai-specs/{agents,skills,commands}/`) — the toolkit "owns" these. On `update` they are **copied verbatim and overwritten** into the consumer's `ai-specs/`. Treat them like a dependency: in a consumer repo you never edit them in place; in *this* repo they are the source of truth you edit.
2. **Scaffold** (`template/scaffold/`, e.g. `openspec/config.yaml`) — copied **once** and **never overwritten**. Each consumer repo owns its copy and fills it in.
3. **Symlinks** — tool dirs like `.claude/` are not copies. `ensureSymlinks` creates symlinks from `.claude/{agents,skills,commands}/<entry>` back into `../../ai-specs/<cat>/<entry>`, so updating the real file in `ai-specs/` updates what every agent tool reads, with no duplication.

`MANAGED_CATEGORIES` and `AGENT_TOOLS` (top of `init.js`) drive this. `AGENT_TOOLS` maps a tool name (`claude`) to its dir and the categories it consumes.

### Ticket systems

`template/ai-specs/tickets/<system>/` holds per-ticket-system files (currently only `jira`). At install time the chosen system's files (`ticket-template.md`, `ticket-system.md`) are resolved to **system-neutral paths** the commands reference — they land as `ai-specs/ticket-template.md` and `ai-specs/ticket-system.md`. The commands never hardcode a ticket system; they read `ai-specs/ticket-system.md` for how to extract a key and fetch a ticket. The `tickets/` dir itself is excluded from symlinking (see the skip in `ensureSymlinks`).

### Config

`.sdd-toolkit.json` in the consumer repo records `{ version, agents, ticketSystem }`. `update` reads it to know which agents/ticket system to refresh and reports the `old -> new` version.

### The shipped workflow (context for editing the assets)

The assets encode a chain the consumer repo uses: `/implement <ticket>` reads a ticket → creates a branch → runs `/opsx:propose` (generates `proposal.md` / `design.md` / `tasks.md` via the `openspec` CLI) → runs the **`spec-reviewer`** subagent in a fresh context for an independent adversarial review → **stops for human approval** → `/opsx:apply` implements. The commands (`commands/`) and skills (`skills/openspec-*`) are near-parallel; `/implement` orchestrates the opsx flow rather than reimplementing it.

The shipped assets are deliberately **repo- and ticket-system agnostic**: they defer to the *consumer* repo's `CLAUDE.md`/`AGENTS.md` for branch naming, conventions, and lint, and to `ai-specs/ticket-system.md` for ticket access. When editing them, preserve that agnosticism — don't bake in assumptions from any one consumer repo.

## Editing conventions

- **To change a shipped asset, edit the file under `template/`** — never model it as something generated. What's in `template/` is exactly what consumers receive.
- **Adding an agent tool** (e.g. Cursor): add an entry to `AGENT_TOOLS` in `bin/init.js` mapping its dir and consumed categories. No consumer code change beyond `--agents=claude,cursor`.
- **Adding a ticket system** (e.g. Linear): create `template/ai-specs/tickets/<system>/` with `ticket-template.md` and `ticket-system.md`. Consumers opt in via `--tickets=<system>`.
- Bump `version` in `package.json` when changing managed assets — that version is what `update` records and reports.
- `README.md` is the user-facing install/update guide; keep it in sync when the install model changes.
