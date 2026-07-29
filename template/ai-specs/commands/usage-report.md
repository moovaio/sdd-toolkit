---
name: "Time and cost report"
description: Report wall-clock time, model time, tokens and dollar cost for this session or a whole ticket cycle, broken down by phase.
category: Analysis
tags: [analysis, cost, usage]
---

Audit what a session — or a whole ticket cycle — actually cost, from the Claude Code
transcripts on disk. Measured, not estimated.

**Input**: optionally a ticket key (`/usage-report MOOV-5147`) to cover the entire cycle
even if it ran across several sessions. With no argument, reports the current session.

---

## Steps

1. **Follow the `sdd-usage-report` skill** — run its script, don't recompute the totals
   yourself. The transcript format has three counting traps the script handles.

   ```bash
   # a ticket key in $ARGUMENTS -> the whole cycle, grouped by command
   python3 ai-specs/skills/sdd-usage-report/report.py --ticket <KEY> --phases command

   # no argument -> the current session, one row per turn
   python3 ai-specs/skills/sdd-usage-report/report.py
   ```

2. **Show the tables as the script printed them.** Do not re-render, re-bucket, or
   rename phases to make the story tidier.

3. **Add a short read** — two or three sentences on where the time and money went and
   what would change it. Cache read dominating means the session was long, not that
   the turns were wasteful; the lever there is cutting the cycle at the approval gates.

4. **Carry the script's caveats into your summary**: the pricing date it used, and — when
   the current session is included — that the turns generating this report are not yet
   written to the transcript, so its own row is partial.

**Guardrails**
- This is an on-demand audit. Never run it as part of `/ticket` or `/implement`.
- Never quote dollar figures without saying which pricing date they came from.
- If the script finds no transcripts, say so plainly rather than estimating from memory.
