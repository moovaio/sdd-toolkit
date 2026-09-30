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
| **Agents** | `spec-reviewer` — independent reviewer of an OpenSpec change (the plan), run by default; `code-reviewer` — independent reviewer of the implementation diff (the code), suggested and run on request |
| **Skills** | `openspec-propose`, `openspec-apply-change`, `openspec-archive-change`, `openspec-explore`, `sdd-usage-report` (measured time/token/dollar cost of a session or cycle) |
| **Commands** | `/ticket` (idea → grounded draft → create ticket), `/implement` (ticket → branch → OpenSpec → spec review → code → suggested code review), `/usage-report` (what a cycle cost), `/daily` (what you did on a day, for the daily), `/opsx:*` |
| **Tickets** | Per-system profile + template. Natively supported: `jira`, `trello` (default: `jira`). Any other value installs a generic fallback you wire up by hand. |
| **Scaffold** | `openspec/config.yaml` starter (copied once, you fill it in) |

## The workflow

The assets encode one chain, from a plain-language idea to an open PR. Two **independent,
fresh-context reviews** frame the implementation — `spec-reviewer` validates the *plan* before
any code is written (**by default**, skipped only when a change is both small and mechanical),
and `code-reviewer` validates the *code* before it becomes a PR (**suggested**, run only if you
ask) — and the flow **stops for a human** (🛑) at every irreversible or outward-facing step.

```mermaid
flowchart TD
    A([Idea in plain language]) --> T1["/ticket &lt;idea&gt;"]

    subgraph TICKET["/ticket — draft &amp; create the ticket"]
        T1 --> T2["Clarify the idea<br/>(ask if ambiguous)"]
        T2 --> T3["Ground it in the codebase<br/>read CLAUDE.md/AGENTS.md + explore real modules"]
        T3 --> T4["Draft using ai-specs/ticket-template.md"]
        T4 --> T5{{"🛑 Human approves the draft"}}
        T5 -->|requests changes| T4
        T5 -->|approves| T6["Create via ai-specs/ticket-system.md"]
    end

    T6 --> K([Ticket created: key + URL])
    K --> I1["/implement &lt;key&gt;"]

    subgraph IMPL["/implement — implement the ticket"]
        I1 --> I2["Read the ticket<br/>(ai-specs/ticket-system.md)"]
        I2 --> I3["Pre-flight git<br/>clean tree, fetch default branch"]
        I3 --> I4{{"🛑 Confirm branch name"}}
        I4 -->|approves| I5["git checkout -b &lt;branch&gt;<br/>from origin/default — includes the key"]
        I5 --> I6["/opsx:propose<br/>proposal.md · design.md · tasks.md"]
        I6 --> I7["spec-reviewer<br/>independent review of the PLAN<br/>(fresh context, runs by default)"]
        I6 -.->|"small + mechanical change"| I8
        I7 --> I8{{"🛑 Human approves the artifacts<br/>(with the review in hand)"}}
        I8 -->|requests changes| I6
        I8 -->|approves| I9["/opsx:apply<br/>implement tasks, [ ]→[x]"]
        I8 -.- S1["↻ fresh session suggested here<br/>the approved artifacts on disk<br/>are the whole handoff"]
        I9 --> I10{{"🛑 Human approves the code<br/>(code-reviewer suggested, not run)"}}
        I10 -.->|"you ask for it"| I10b["code-reviewer<br/>independent review of the CODE/diff<br/>(fresh context) + optional /security-review"]
        I10b -.-> I10
        I10 -->|requests changes| I9
        I10 -->|approves| I12["Wrap up · lint · final task progress"]
    end

    I12 --> P1{{"🛑 Commit / push only when you ask"}}
    P1 --> P2["git push + open PR<br/>per the repo's conventions"]
    P2 --> PR([PR opened])
    P2 -.-> AR["/opsx:archive<br/>(once the change is done)"]

    style TICKET fill:#eef6ff,stroke:#4285f4
    style IMPL fill:#f0fdf4,stroke:#34a853
    style T5 fill:#fff4e5,stroke:#f5a623
    style I4 fill:#fff4e5,stroke:#f5a623
    style I8 fill:#fff4e5,stroke:#f5a623
    style I10 fill:#fff4e5,stroke:#f5a623
    style P1 fill:#fff4e5,stroke:#f5a623
    style S1 fill:#f7f7f7,stroke:#999,color:#555
```

The reviews feed back: an `APPROVE-WITH-CHANGES` / `REJECT` verdict loops back to fix the
artifacts (spec) or the code before asking for approval. Creating the ticket and opening the PR
are outward-facing — the flow never does them without your say-so. The code review is offered at
the last gate rather than run for you: ask for it when the diff warrants a second pair of eyes.

The human gates are also the cheap places to **split the cycle across sessions**, which is why
`/implement` suggests it there. Every turn re-reads the whole conversation before it, so a
single session that runs from ticket to PR pays for the ticket fetch and the codebase
exploration on every implementation turn. At the artifact gate, `openspec/changes/<name>/` is
already the complete handoff — `/opsx:apply` needs nothing from that conversation. It stays a
suggestion: if you'd rather keep going in one session, the flow continues without asking twice.

## What you did yesterday

`/daily` rebuilds a day from git history and the ticket system, as a short summary to read out at
the daily: what you worked on, what reached dev, what reached production, and tickets you created.

```bash
/daily              # the previous working day (on Monday, the Friday before)
/daily 2026-09-25   # a specific day
```

It is read-only and covers the current repo. The dev and production branches are configurable in the
repo's `CLAUDE.md` / `AGENTS.md`:

```markdown
## Environment branches
- dev: `dev`
- production: `master`
```

Without that note it defaults to the first existing of `dev`/`develop`/`development`/`staging` and
`master`/`main`/`production`, and offers to record what it found. The ticket query comes from the "Listing recent activity" section of `ai-specs/ticket-system.md` —
without one, the summary is from git alone.

## What a cycle costs

`/usage-report` measures it from the Claude Code transcripts on disk — wall-clock time, model
time (wall-clock minus the time it spent waiting on you), tokens and dollars, per phase, with
each subagent itemized.

```bash
/usage-report              # the current session
/usage-report MOOV-5147    # the whole cycle, even if it ran across several sessions
```

It selects a cycle by matching the ticket key against the git branch recorded in every
transcript row, so splitting the cycle into sessions doesn't hide anything from the report.
Read the `cache read` column first — it is normally the largest line, it is context re-read on
every turn, and it grows with session length. When it dominates, the lever is shorter sessions
rather than fewer tokens per turn.

The skill runs a bundled script (`report.py`, stdlib only) rather than deriving the numbers in
prose, because three details of the transcript format make hand-counting wrong by 2–8×: one API
request writes one row per content block and **every row repeats the full `usage`** (group by
`message.id`), `output_tokens` grows across those rows so only the last is final (take the max),
and `toolUseResult.totalTokens` on a Task result is a subagent's **last turn**, not its total
(the real figures are in `<session>/subagents/agent-*.jsonl`). The script prints the pricing
date it used — confirm current rates before quoting dollars.

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
`old -> new` version. Managed assets the toolkit no longer ships (renamed or dropped, e.g. `/tasks`
→ `/daily`) are removed along with their `.claude/` symlinks. Anything you added to `ai-specs/`
yourself, your scaffold files and OpenSpec content are never touched.

## How it works

- **Managed assets** (agents / skills / commands) are the real files, kept in `ai-specs/`
  inside the repo. `update` overwrites them — treat them like a dependency, don't edit in place.
- **Tool dirs** (`.claude/`) are **symlinks** into `ai-specs/`, so updating the real file
  updates what every agent tool reads. No duplication.
- **Scaffold files** (`openspec/config.yaml`) are copied once and never overwritten.
- **Config** lives in `.sdd-toolkit.json`: `{ version, agents, ticketSystem, ticketSupported, managedFiles }`.
  `ticketSupported` records whether the chosen ticket system shipped with the toolkit; it is what
  makes `update` overwrite a supported system's profile but leave a hand-filled fallback alone.
  `managedFiles` lists the toolkit-owned files installed, so `update` knows which ones to remove
  when a later version stops shipping them.

```
your-repo/
  ai-specs/                    # managed source of truth (committed)
    agents/{spec-reviewer.md,code-reviewer.md}
    skills/openspec-*/
    skills/sdd-usage-report/    # SKILL.md + report.py
    commands/{ticket.md,implement.md,usage-report.md,tasks.md,opsx/*}
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
