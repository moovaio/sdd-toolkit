---
name: sdd-usage-report
description: Report the time and dollar cost of a Claude Code session or a whole ticket cycle, broken down by phase, with subagents itemized. Run it ONLY when explicitly asked (e.g. "how much did this cost", "hacé el reporte de tiempos y costos", `/usage-report`) — it is an on-demand audit, never part of the SDD workflow.
compatibility: Requires python3 (standard library only) and Claude Code transcripts under ~/.claude/projects/.
metadata:
  author: moova
  version: "1.0"
---

Measure what a session or a ticket cycle actually cost — wall-clock time, model time,
tokens and dollars — from the Claude Code transcripts on disk. Nothing here is estimated.

**Run the bundled script. Do not hand-compute totals from the transcript.**

```bash
python3 ai-specs/skills/sdd-usage-report/report.py [options]
```

| Selector | What it reports |
|---|---|
| *(none)* | The current session (most recently written transcript) |
| `--ticket MOOV-1234` | Every session whose git branch names that ticket — the whole cycle, even if it was split across sessions |
| `--session <uuid>` | One specific session |
| `--last N` | The N most recent sessions in this repo |

Other flags: `--phases command` groups phases by slash command instead of one per
human turn (use it for a cycle-level report — it is the shape people expect);
`--phases turn` is the default and hides nothing; `--json` for machine-readable output;
`--project <dir>` to report on a different repo.

## Why a script and not prose

Three details in the transcript format make hand-counting wrong by 2–8×. The script
enforces them; a re-derivation usually does not.

1. **One API request writes many rows.** Each content block (thinking, text, each
   `tool_use`) gets its own row, and every row repeats the *full* `usage` object.
   Counting rows inflates everything — group by `message.id`.
2. **`output_tokens` grows across those rows.** Only the last row of a request holds
   the final count; earlier rows hold partials. Take the max, not the first or the sum.
3. **`toolUseResult.totalTokens` on a Task result is the subagent's last turn, not its
   total.** It can under-report by 8×. The real numbers are in
   `<session>/subagents/agent-*.jsonl`, which the script reads.

## Reading the result

- **Reloj vs Modelo** — wall-clock for the phase vs that minus the time the session
  spent waiting for a human to read and reply. The gap is human time, not slowness.
- **Cache read is normally the largest line.** It is context re-read on every turn and
  it grows with session length: each new turn re-reads everything before it. When it
  dominates, the lever is *shorter sessions*, not fewer tokens per turn — the natural
  cut points in this workflow are the human approval gates, where the artifacts on
  disk already carry the full state.
- **Subagents** are listed separately but their cost is already inside the phase where
  they ran, so the phase table still totals correctly. Do not add them again.

## Reporting honestly

- The script prints the pricing date it used. If that date is old, confirm the rates
  against current pricing before quoting dollars to anyone, and say which rates you used.
- When the current session is included, its final turns — including the ones producing
  the report — are **not yet on disk**. The script says so; keep that caveat in your
  summary instead of presenting a closed total.
- Do not invent phase names or re-bucket the numbers to tell a tidier story. If a phase
  label is unhelpful, say what happened in it; leave the measured boundaries alone.
