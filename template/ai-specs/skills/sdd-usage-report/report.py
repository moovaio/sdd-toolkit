#!/usr/bin/env python3
"""Aggregate time and token cost from Claude Code transcripts.

Reads the JSONL transcripts under ~/.claude/projects/<project>/ and reports
wall-clock time, model time, tokens and dollar cost, split into phases.
Subagents are read from their own transcripts, not from the (under-reporting)
`totalTokens` field of the Task tool result.

Usage:
  report.py                        # current session (most recently written)
  report.py --ticket MOOV-5147     # every session whose git branch names the ticket
  report.py --session <uuid>       # one session by id
  report.py --last 3              # the N most recent sessions
  report.py --phases command      # group phases by slash command instead of per turn
  report.py --json                # machine-readable output

Three aggregation invariants this script exists to enforce — get any of them
wrong and the numbers are off by 2-8x:

1. One API request writes MANY transcript rows (one per content block), and
   every row repeats the full `usage`. Group by `message.id`, never sum rows.
2. Within one `message.id`, `output_tokens` grows across rows; only the last
   row holds the final count. Take the max.
3. `toolUseResult.totalTokens` on a Task result is the subagent's LAST turn,
   not its total. Read <session>/subagents/agent-*.jsonl instead.
"""

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Pricing, $ per 1M tokens, as of 2026-07. Cache read is 0.1x the input rate,
# 5-minute cache writes 1.25x, 1-hour cache writes 2x.
# Confirm against https://platform.claude.com/docs/en/pricing before quoting
# these figures externally — rates change and this table is a local copy.
PRICING = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
PRICING_DATE = "2026-07"
DEFAULT_RATE = (5.0, 25.0)


def rates(model):
    """Base (input, output) $/MTok for a model id, ignoring any [1m] suffix."""
    if not model:
        return DEFAULT_RATE
    return PRICING.get(model.split("[")[0], DEFAULT_RATE)


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Loading


def project_dir(cwd):
    """Find the transcript directory for a working directory.

    Tries the slug Claude Code derives from the path, then falls back to
    matching the `cwd` field recorded inside each project's transcripts.
    """
    root = os.path.realpath(os.path.expanduser("~/.claude/projects"))
    # Claude Code slugs the path by replacing every non [A-Za-z0-9-] char
    # (including dots: moova.io -> moova-io). Resolve and confine the result
    # to the projects root so a crafted --project can't escape it.
    slug = os.path.realpath(
        os.path.join(root, re.sub(r"[^A-Za-z0-9-]", "-", cwd))
    )
    if os.path.commonpath([slug, root]) == root and os.path.isdir(slug):
        return slug
    for candidate in sorted(glob.glob(os.path.join(root, "*"))):
        candidate = os.path.realpath(candidate)
        if os.path.commonpath([candidate, root]) != root:
            continue
        if not os.path.isdir(candidate):
            continue
        files = glob.glob(os.path.join(candidate, "*.jsonl"))
        if not files:
            continue
        try:
            with open(files[0], encoding="utf-8") as fh:
                for line in fh:
                    if line.strip() and json.loads(line).get("cwd") == cwd:
                        return candidate
                    break
        except (OSError, ValueError):
            continue
    return None


def rows(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue  # a partially flushed final line
    except OSError:
        pass
    return out


def api_requests(rows_, agent=None):
    """Collapse assistant rows into one record per API request.

    Invariants 1 and 2 live here. In a main transcript, `isSidechain` rows are
    a subagent's turns mirrored into the parent and are skipped — they are
    counted from the subagent's own transcript instead. A subagent transcript
    is entirely `isSidechain`, so the filter only applies to the parent.
    """
    by_id = {}
    for row in rows_:
        if row.get("type") != "assistant":
            continue
        if agent is None and row.get("isSidechain"):
            continue
        message = row.get("message") or {}
        usage = message.get("usage")
        mid = message.get("id")
        if not usage or not mid:
            continue
        creation = usage.get("cache_creation") or {}
        record = {
            "at": ts(row["timestamp"]),
            "model": message.get("model"),
            "agent": agent,
            "effort": row.get("effort"),
            "input": usage.get("input_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "write_5m": creation.get("ephemeral_5m_input_tokens", 0),
            "write_1h": creation.get("ephemeral_1h_input_tokens", 0),
            "output": usage.get("output_tokens", 0),
        }
        previous = by_id.get(mid)
        # Same request, later row: keep the highest output count seen.
        if previous is None or record["output"] > previous["output"]:
            if previous is not None:
                record["at"] = previous["at"]
            by_id[mid] = record
    return sorted(by_id.values(), key=lambda r: r["at"])


def subagent_requests(session_path):
    """Read each subagent's own transcript (invariant 3)."""
    out = []
    subdir = session_path[: -len(".jsonl")] + "/subagents"
    for path in sorted(glob.glob(os.path.join(subdir, "agent-*.jsonl"))):
        meta_path = path[: -len(".jsonl")] + ".meta.json"
        label = "subagent"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as fh:
                    label = json.load(fh).get("agentType") or label
            except (OSError, ValueError):
                pass
        out.extend(api_requests(rows(path), agent=label))
    return out


# ---------------------------------------------------------------------------
# Phases


def human_turns(rows_):
    """User messages that a person actually typed, in order.

    Excludes tool results (list content) and harness-injected stdout rows.
    """
    turns = []
    for row in rows_:
        if row.get("type") != "user" or row.get("isSidechain"):
            continue
        content = (row.get("message") or {}).get("content")
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text or text.startswith("<local-command"):
            continue
        command = None
        if "<command-name>" in text:
            start = text.index("<command-name>") + len("<command-name>")
            command = text[start : text.index("</command-name>", start)].strip()
        turns.append({"at": ts(row["timestamp"]), "command": command, "text": text})
    return turns


def label_of(turn):
    if turn["command"]:
        return turn["command"]
    first = turn["text"].splitlines()[0].strip()
    return first[:38] + ("…" if len(first) > 38 else "")


def phases(rows_, mode):
    """Phase boundaries. Each phase starts at a human turn.

    mode="turn": one phase per human turn — faithful, never hides anything.
    mode="command": a new phase only on a slash command; plain turns continue
      the current phase. Fewer rows, matches how a cycle reads.
    """
    turns = human_turns(rows_)
    if not turns:
        return []
    out = []
    for turn in turns:
        if mode == "command" and out and not turn["command"]:
            continue
        out.append({"label": label_of(turn), "start": turn["at"]})
    if mode == "command" and not turns[0]["command"]:
        out[0]["label"] = "conversación · " + out[0]["label"]
    return out


# ---------------------------------------------------------------------------
# Cost


def cost_of(request):
    rate_in, rate_out = rates(request["model"])
    return (
        request["input"] * rate_in
        + request["cache_read"] * rate_in * 0.1
        + request["write_5m"] * rate_in * 1.25
        + request["write_1h"] * rate_in * 2.0
        + request["output"] * rate_out
    ) / 1e6


def blank():
    return {
        "requests": 0,
        "input": 0,
        "cache_read": 0,
        "cache_write": 0,
        "output": 0,
        "cost": 0.0,
    }


def add(bucket, request):
    bucket["requests"] += 1
    bucket["input"] += request["input"]
    bucket["cache_read"] += request["cache_read"]
    bucket["cache_write"] += request["write_5m"] + request["write_1h"]
    bucket["output"] += request["output"]
    bucket["cost"] += cost_of(request)


# ---------------------------------------------------------------------------
# Rendering


def minutes(seconds):
    return f"{seconds / 60:.1f} m"


def thousands(value):
    return f"{value:,}".replace(",", ".")


def millions(value):
    if value >= 1e6:
        return f"{value / 1e6:.1f} M"
    if value >= 1e3:
        return f"{value / 1e3:.0f} k"
    return str(value)


def table(headers, body, aligns):
    widths = [len(h) for h in headers]
    for line in body:
        for i, cell in enumerate(line):
            widths[i] = max(widths[i], len(str(cell)))

    def rule(left, mid, right):
        return left + mid.join("─" * (w + 2) for w in widths) + right

    def row(cells):
        parts = []
        for cell, width, align in zip(cells, widths, aligns):
            text = str(cell)
            parts.append(
                " " + (text.ljust(width) if align == "l" else text.rjust(width)) + " "
            )
        return "│" + "│".join(parts) + "│"

    lines = [rule("┌", "┬", "┐"), row(headers), rule("├", "┼", "┤")]
    for line in body:
        lines.append(row(line))
    lines.append(rule("└", "┴", "┘"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------


def analyse(session_paths, mode):
    all_rows = []
    requests = []
    subagents = {}
    for path in session_paths:
        session_rows = rows(path)
        all_rows.extend(session_rows)
        requests.extend(api_requests(session_rows))
        for request in subagent_requests(path):
            requests.append(request)
            bucket = subagents.setdefault(request["agent"], blank())
            add(bucket, request)

    all_rows.sort(key=lambda r: r.get("timestamp") or "")
    requests.sort(key=lambda r: r["at"])
    if not requests:
        return None

    marks = phases(all_rows, mode)
    if not marks:
        marks = [{"label": "sesión", "start": requests[0]["at"]}]
    # Anything before the first human turn (a resumed session, a hook) still counts.
    if requests[0]["at"] < marks[0]["start"]:
        marks.insert(0, {"label": "previo", "start": requests[0]["at"]})

    last = max(r["at"] for r in requests)
    for i, mark in enumerate(marks):
        mark["end"] = marks[i + 1]["start"] if i + 1 < len(marks) else last
        mark["totals"] = blank()
        mark["waiting"] = 0.0

    def phase_of(at):
        target = marks[0]
        for mark in marks:
            if at >= mark["start"]:
                target = mark
            else:
                break
        return target

    for request in requests:
        add(phase_of(request["at"])["totals"], request)

    # Time spent waiting for the person: the gap between the last thing the
    # session wrote and the moment they replied. Charged to the phase the
    # session was sitting in when it started waiting, so a phase's model time
    # stays honest whichever granularity is in use.
    stamped = [ts(r["timestamp"]) for r in all_rows if r.get("timestamp")]
    for turn in human_turns(all_rows):
        before = [t for t in stamped if t < turn["at"]]
        if not before:
            continue
        previous = max(before)
        gap = (turn["at"] - previous).total_seconds()
        if gap > 0:
            phase_of(previous)["waiting"] += gap

    return {
        "phases": marks,
        "requests": requests,
        "subagents": subagents,
        "models": sorted({r["model"] for r in requests if r["model"]}),
        "wall": (last - marks[0]["start"]).total_seconds(),
    }


def render(result, session_paths, live):
    marks = result["phases"]
    body = []
    totals = blank()
    wall_sum = model_sum = 0.0
    for mark in marks:
        wall = (mark["end"] - mark["start"]).total_seconds()
        model = max(wall - mark["waiting"], 0.0)
        wall_sum += wall
        model_sum += model
        t = mark["totals"]
        for key in totals:
            totals[key] += t[key]
        body.append(
            [
                mark["label"],
                minutes(wall),
                minutes(model),
                thousands(t["output"]),
                millions(t["cache_read"]),
                f"${t['cost']:.2f}",
            ]
        )
    body.append(
        [
            "TOTAL",
            minutes(wall_sum),
            minutes(model_sum),
            thousands(totals["output"]),
            millions(totals["cache_read"]),
            f"${totals['cost']:.2f}",
        ]
    )

    out = []
    out.append(
        table(
            ["Fase", "Reloj", "Modelo", "Output tok", "Cache read", "Costo"],
            body,
            ["l", "r", "r", "r", "r", "r"],
        )
    )

    human = wall_sum - model_sum
    share = (human / wall_sum * 100) if wall_sum else 0
    out.append("")
    out.append(
        f"{totals['requests']} requests a la API · "
        f"{minutes(human)} ({share:.0f}%) esperando a la persona · "
        f"modelos: {', '.join(result['models'])}"
    )

    if result["subagents"]:
        out.append("")
        out.append("Subagentes (su costo ya está sumado en las fases de arriba):")
        sub_body = []
        for name, bucket in sorted(
            result["subagents"].items(), key=lambda kv: -kv[1]["cost"]
        ):
            sub_body.append(
                [
                    name,
                    str(bucket["requests"]),
                    thousands(bucket["output"]),
                    millions(bucket["cache_read"]),
                    f"${bucket['cost']:.2f}",
                ]
            )
        out.append(
            table(
                ["Agente", "Req", "Output tok", "Cache read", "Costo"],
                sub_body,
                ["l", "r", "r", "r", "r"],
            )
        )

    read_cost = sum(
        r["cache_read"] * rates(r["model"])[0] * 0.1 / 1e6 for r in result["requests"]
    )
    if totals["cost"]:
        per_request = totals["cache_read"] // max(totals["requests"], 1)
        out.append("")
        out.append(
            f"El cache read son ${read_cost:.2f} de los ${totals['cost']:.2f} "
            f"({read_cost / totals['cost'] * 100:.0f}%): contexto re-leído en cada "
            f"turno, ~{thousands(per_request)} tokens por request."
        )

    out.append("")
    out.append(
        f"Precios locales de {PRICING_DATE}; {len(session_paths)} "
        f"{'sesión' if len(session_paths) == 1 else 'sesiones'} analizada"
        f"{'' if len(session_paths) == 1 else 's'}."
    )
    if live:
        out.append(
            "La sesión en curso está incluida hasta este momento — los turnos que "
            "generan este reporte todavía no están escritos en el transcript."
        )
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ticket", help="ticket key to match against git branches")
    group.add_argument("--session", help="session id (uuid)")
    group.add_argument("--last", type=int, metavar="N", help="N most recent sessions")
    parser.add_argument(
        "--phases",
        choices=["turn", "command"],
        default="turn",
        help="phase granularity (default: one per human turn)",
    )
    parser.add_argument("--project", help="working directory (default: cwd)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    cwd = os.path.abspath(args.project or os.getcwd())
    directory = project_dir(cwd)
    if not directory:
        sys.exit(f"No hay transcripts para {cwd} en ~/.claude/projects/")

    files = sorted(
        glob.glob(os.path.join(directory, "*.jsonl")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not files:
        sys.exit(f"No hay transcripts en {directory}")
    newest = files[0]

    if args.session:
        selected = [p for p in files if args.session in os.path.basename(p)]
        if not selected:
            sys.exit(f"No encontré la sesión {args.session}")
    elif args.ticket:
        key = args.ticket.lower()
        selected = []
        for path in files:
            for row in rows(path):
                branch = (row.get("gitBranch") or "").lower()
                if key in branch:
                    selected.append(path)
                    break
        if not selected:
            sys.exit(f"Ninguna sesión con {args.ticket} en su rama de git")
    elif args.last:
        selected = files[: args.last]
    else:
        selected = [newest]

    selected = sorted(selected, key=os.path.getmtime)
    result = analyse(selected, args.phases)
    if not result:
        sys.exit("Las sesiones seleccionadas no tienen requests con usage")

    if args.json:
        print(
            json.dumps(
                {
                    "sessions": [os.path.basename(p) for p in selected],
                    "pricing_date": PRICING_DATE,
                    "models": result["models"],
                    "wall_seconds": result["wall"],
                    "phases": [
                        {
                            "label": m["label"],
                            "start": m["start"].isoformat(),
                            "wall_seconds": (m["end"] - m["start"]).total_seconds(),
                            "model_seconds": max(
                                (m["end"] - m["start"]).total_seconds()
                                - m["waiting"],
                                0.0,
                            ),
                            **m["totals"],
                        }
                        for m in result["phases"]
                    ],
                    "subagents": result["subagents"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(render(result, selected, live=newest in selected))


if __name__ == "__main__":
    main()
