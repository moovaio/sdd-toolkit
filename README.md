# sdd-toolkit

Moova's **Spec-Driven Development** toolkit. It bundles the agents, skills and slash
commands for the OpenSpec workflow so any repo can share the exact same setup, and
pull updates centrally when the toolkit changes.

## Prerequisites

- **Node >= 18** (to run the installer via `npx`).
- **OpenSpec CLI** — the OpenSpec commands this toolkit ships need it installed. See the docs at
  <https://openspec.dev/>, or install it directly:

  ```bash
  npm install -g @fission-ai/openspec@latest
  ```

## What it ships

| Category | Assets |
|----------|--------|
| **Agents** | `spec-reviewer` — independent, adversarial reviewer of an OpenSpec change |
| **Skills** | `openspec-propose`, `openspec-apply-change`, `openspec-archive-change`, `openspec-explore` |
| **Commands** | `/ticket` (idea → grounded draft → create ticket), `/implement` (ticket → branch → OpenSpec → review → code), `/opsx:*` |
| **Tickets** | Per-system profile + template. Natively supported: `jira`, `trello` (default: `jira`). Any other value installs a generic fallback you wire up by hand. |
| **Scaffold** | `openspec/config.yaml` starter (copied once, you fill it in) |

## Install into a repo (once)

From the root of the target repo:

```bash
npx github:moovaio/sdd-toolkit init
```

Defaults to `--agents=claude --tickets=jira`. Override either:

```bash
npx github:moovaio/sdd-toolkit init --agents=claude --tickets=trello
```

`--tickets` accepts a natively-supported system (`jira`, `trello`) or **any other name**. If it's
not supported (e.g. `--tickets=osticket`), the installer still proceeds: it prints a warning with
the manual steps and installs a generic fallback profile at `ai-specs/ticket-system.md` for you to
fill in. Those fallback files are yours — `update` never overwrites them.

Then commit `ai-specs/`, `.claude/` and `.sdd-toolkit.json`. The whole team gets the
setup by cloning — nobody else needs to run the command.

## Update to the latest toolkit version

```bash
npx github:moovaio/sdd-toolkit update            # apply
npx github:moovaio/sdd-toolkit update --dry-run  # preview what would change
```

`update` reads `.sdd-toolkit.json`, refreshes the **managed** assets, and reports
`old -> new` version. Your scaffold files and OpenSpec content are never touched.

## How it works

- **Managed assets** (agents / skills / commands) are the real files, kept in `ai-specs/`
  inside the repo. `update` overwrites them — treat them like a dependency, don't edit in place.
- **Tool dirs** (`.claude/`) are **symlinks** into `ai-specs/`, so updating the real file
  updates what every agent tool reads. No duplication.
- **Scaffold files** (`openspec/config.yaml`) are copied once and never overwritten.
- **Config** lives in `.sdd-toolkit.json`: `{ version, agents, ticketSystem }`.

```
your-repo/
  ai-specs/                    # managed source of truth (committed)
    agents/spec-reviewer.md
    skills/openspec-*/
    commands/{implement.md,opsx/*}
    ticket-template.md         # resolved from the chosen ticket system
  .claude/                     # symlinks -> ai-specs/
    agents/…  skills/…  commands/…
  openspec/config.yaml         # scaffold (yours to fill)
  .sdd-toolkit.json
```

## Extending

- **New agent tool** (e.g. Cursor): add an entry to `AGENT_TOOLS` in `bin/init.js`
  mapping the tool's dir and the categories it consumes, then consumers set
  `--agents=claude,cursor`.
- **New ticket system** (e.g. Linear): add a `template/ai-specs/tickets/<system>/` folder with
  `ticket-template.md` and `ticket-system.md` (how `/implement` reads a ticket), and consumers set
  `--tickets=<system>`. Dirs starting with `_` are internal (the `_unsupported` fallback), not
  selectable systems. Consumers who need a one-off system don't have to wait for this — they can pass
  any `--tickets=<name>` and edit the generic fallback profile in their repo.
