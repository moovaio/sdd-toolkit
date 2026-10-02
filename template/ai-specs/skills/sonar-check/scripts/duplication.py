#!/usr/bin/env python3
"""
Estimate SonarQube Cloud's `new_duplicated_lines_density` for a PR diff.

Sonar detects a duplication when >= MIN_TOKENS successive tokens repeat across
at least MIN_LINES lines. The copy-paste index covers the WHOLE project, not
just the changed files, so a single new file that clones an existing one scores
as fully duplicated even when nothing else in the diff is.

Only lines the diff adds count toward `new_duplicated_lines`; the density is
that count over the added lines of the files Sonar tokenizes.

The 95-token default was calibrated on a PHP codebase against PRs whose real
density SonarCloud had already reported: it reproduced the pass/fail verdict on
all of them. Sonar's own documented threshold is 100 tokens, but its PHP
tokenizer splits slightly differently than token_get_all, so 95 of our tokens
lands on their 100. Languages other than PHP go through a generic tokenizer and
are uncalibrated until a repo records its own evidence (see the skill's
"Calibrating" section).

Usage:
    duplication.py --base <sha> --head <sha> [--json] [--min-tokens N] [--min-lines N]
    duplication.py --base <sha>                      # head = working tree

Exit code is 1 when the estimated density exceeds --threshold (default 3.0).
"""
import argparse
import json
import os
import subprocess
import sys
import re
import tarfile
import tempfile
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENIZER = os.path.join(HERE, "tokenize.php")

# What each language group contributes to the copy-paste index. PHP goes through
# token_get_all; everything else uses the generic tokenizer below.
LANGS = {
    "php": (".php",),
    "groovy": (".groovy", "Jenkinsfile"),
    "markdown": (".md",),
    "js": (".js", ".ts", ".vue"),
    "web": (".blade.php", ".html", ".css", ".scss"),
    "xml": (".xml", ".xsd"),
    "yaml": (".yml", ".yaml"),
    "json": (".json",),
    "sql": (".sql",),
    "python": (".py",),
}
DEFAULT_LANGS = ("php", "groovy", "js", "sql")

GENERIC_TOKEN = re.compile(
    r'''"[^"\n]*"|\'[^\'\n]*\'|[A-Za-z_]\w*|\d+(?:\.\d+)?|\S''', re.ASCII
)


def matches(path, extensions):
    return path.endswith(extensions) or os.path.basename(path) in extensions


def tokenize_generic(real_path):
    """
    Line-aware tokenizer for the languages we do not have a real parser for.

    Same normalization as the PHP side: quoted strings and numbers collapse to a
    placeholder so a copied block survives having its literals swapped.
    """
    try:
        with open(real_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return []
    out = []
    for lineno, text in enumerate(content.splitlines(), start=1):
        for tok in GENERIC_TOKEN.findall(text):
            if tok[0] in "\"'" or tok[0].isdigit():
                tok = "$LIT"
            out.append((lineno, tok))
    return out


def commit(ref):
    """
    Resolve a user-supplied ref to the commit SHA git itself reports.

    Only that SHA ever reaches a git command line, so a value such as
    `--output=<path>` can never be read as an option instead of a revision.
    """
    if ref.startswith("-"):
        raise argparse.ArgumentTypeError(f"not a revision: {ref}")
    sha = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
        raise argparse.ArgumentTypeError(f"not a commit in this repo: {ref}")
    return sha


def sh(args, cwd=None):
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=False
    ).stdout


def changed_files(base, head, extensions):
    """Added/modified files in the diff, restricted to what Sonar tokenizes."""
    rng = [base] if head is None else [base, head]
    raw = sh(["git", "diff", "--diff-filter=AM", "--name-only", *rng])
    return [f for f in raw.splitlines() if matches(f, extensions)]


def project_files(head, extensions):
    """Every tracked file Sonar tokenizes, at the head revision."""
    ref = "HEAD" if head is None else head
    raw = sh(["git", "ls-tree", "-r", "--name-only", ref])
    return [f for f in raw.splitlines() if matches(f, extensions)]


def added_lines(base, head):
    """
    Line numbers on the head side that the diff adds or modifies, per file.

    One `git diff` for the whole change: a per-file call costs more in process
    spawns than the parsing saves.
    """
    rng = [base] if head is None else [base, head]
    raw = sh(["git", "diff", "--diff-filter=AM", "--unified=0", *rng])
    per_file, current, new_no = defaultdict(set), None, None
    for line in raw.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            new_no = None
        elif line.startswith("@@") and current is not None:
            # @@ -old,cnt +new,cnt @@
            plus = line.split("+", 1)[1].split("@@")[0].strip()
            new_no = int(plus.split(",")[0])
        elif new_no is not None and line.startswith("+"):
            per_file[current].add(new_no)
            new_no += 1
    return per_file


def materialize(head, paths, workdir):
    """
    Copy the head-side content of every path into workdir.

    `git archive` hands us the whole tree in one process instead of one
    `git show` per file.
    """
    if head is None:
        return {p: p for p in paths if os.path.exists(p)}

    globs = sorted({
        ("*" + os.path.splitext(p)[1]) if os.path.splitext(p)[1] else os.path.basename(p)
        for p in paths
    })
    proc = subprocess.run(
        ["git", "archive", "--format=tar", head, "--", *globs],
        capture_output=True, check=False,
    )
    if proc.returncode != 0:
        return {}
    tar_path = os.path.join(workdir, "head.tar")
    with open(tar_path, "wb") as fh:
        fh.write(proc.stdout)
    with tarfile.open(tar_path) as tf:
        # `filter=` only exists from Python 3.12; the archive is our own tree.
        try:
            tf.extractall(workdir, filter="data")
        except TypeError:
            tf.extractall(workdir)
    return {
        p: os.path.join(workdir, p)
        for p in paths
        if os.path.exists(os.path.join(workdir, p))
    }


def tokenize(path_map):
    """
    One PHP process for every .php file; everything else in-process.

    Spawning php per file dominated the runtime, so the tokenizer reads its work
    list from stdin.
    """
    if not path_map:
        return {}

    corpus = {}
    php_map = {}
    for label, real in path_map.items():
        if label.endswith(".php"):
            php_map[label] = real
        else:
            toks = tokenize_generic(real)
            if toks:
                corpus[label] = toks
    if not php_map:
        return corpus

    stdin = "\n".join(f"{label}\t{real}" for label, real in php_map.items())
    raw = subprocess.run(
        ["php", TOKENIZER], input=stdin, capture_output=True, text=True, check=False
    ).stdout

    current = None
    for line in raw.splitlines():
        if line.startswith("#FILE\t"):
            current = line.split("\t", 1)[1]
            corpus[current] = []
            continue
        if current is None:
            continue
        num, _, tok = line.partition("\t")
        try:
            corpus[current].append((int(num), tok))
        except ValueError:
            continue
    return corpus


def find_duplicates(corpus, min_tokens, min_lines):
    """
    corpus: {path: [(line, token), ...]}

    Returns (duplicated_lines, blocks) where duplicated_lines maps a path to the
    set of lines covered by a duplicated block, and blocks describes each pair
    for reporting.

    Windows are indexed by a rolling polynomial hash, then confirmed by comparing
    the real token slices, so a hash collision cannot invent a duplication.
    """
    vocab = {}
    flat = []  # (path, line, token_id)
    for path, toks in corpus.items():
        for line, tok in toks:
            flat.append((path, line, vocab.setdefault(tok, len(vocab) + 1)))

    n = len(flat)
    if n < min_tokens:
        return defaultdict(set), []

    MOD = (1 << 61) - 1
    BASE = 1_000_003
    prefix = [0] * (n + 1)
    for i, (_, _, tid) in enumerate(flat):
        prefix[i + 1] = (prefix[i] * BASE + tid) % MOD
    power = pow(BASE, min_tokens, MOD)

    windows = defaultdict(list)
    for start in range(n - min_tokens + 1):
        end = start + min_tokens - 1
        # A window may not straddle two files.
        if flat[start][0] != flat[end][0]:
            continue
        if flat[end][1] - flat[start][1] + 1 < min_lines:
            continue
        h = (prefix[start + min_tokens] - prefix[start] * power) % MOD
        windows[h].append(start)

    def slice_ids(start):
        return tuple(flat[i][2] for i in range(start, start + min_tokens))

    duplicated = defaultdict(set)
    blocks = []
    for starts in windows.values():
        if len(starts) < 2:
            continue
        exact = defaultdict(list)
        for s in starts:
            exact[slice_ids(s)].append(s)
        for group in exact.values():
            if len(group) < 2:
                continue
            # An occurrence counts as a copy only if some OTHER occurrence sits in
            # a different file, or far enough away in the same one -- a run of
            # identical tokens is not a copy of itself. Judged per occurrence, so
            # lowering min_tokens can only ever find more duplication.
            kept = [
                s for s in group
                if any(t != s and (flat[t][0] != flat[s][0] or abs(t - s) >= min_tokens)
                       for t in group)
            ]
            if len(kept) < 2:
                continue
            for s in kept:
                first, last = flat[s][1], flat[s + min_tokens - 1][1]
                duplicated[flat[s][0]].update(range(first, last + 1))
            blocks.append([
                {"file": flat[s][0], "from": flat[s][1],
                 "to": flat[s + min_tokens - 1][1]}
                for s in kept
            ])
    return duplicated, blocks


def merge_blocks(blocks, new_lines_map):
    """
    Collapse the window-level pairs into readable file-pair ranges.

    Each entry says which side is the diff's own code, so the report can separate
    "what you wrote" from "what it clones".
    """
    by_pair = defaultdict(list)
    for group in blocks:
        key = tuple(sorted({occ["file"] for occ in group}))
        by_pair[key].append(group)
    summary = []
    for key, groups in by_pair.items():
        spans = defaultdict(lambda: [10**9, 0])
        for group in groups:
            for occ in group:
                span = spans[occ["file"]]
                span[0] = min(span[0], occ["from"])
                span[1] = max(span[1], occ["to"])
        new_hits = {
            f: len(new_lines_map.get(f, set()) & set(range(a, b + 1)))
            for f, (a, b) in spans.items()
        }
        summary.append({
            "files": list(key),
            "ranges": {f: f"{a}-{b}" for f, (a, b) in spans.items()},
            "new_lines_in_block": {f: n for f, n in new_hits.items() if n},
            "windows": len(groups),
        })
    return sorted(
        summary,
        key=lambda s: (-sum(s["new_lines_in_block"].values()), -s["windows"]),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=commit)
    ap.add_argument("--head", default=None, type=commit)
    ap.add_argument("--min-tokens", type=int, default=95)
    ap.add_argument("--min-lines", type=int, default=10)
    ap.add_argument("--threshold", type=float, default=3.0)
    ap.add_argument("--langs", default=",".join(DEFAULT_LANGS),
                    help="language groups to index: " + ",".join(LANGS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    extensions = tuple(
        ext for group in args.langs.split(",") if group.strip()
        for ext in LANGS.get(group.strip(), ())
    )
    files = changed_files(args.base, args.head, extensions)
    if not files:
        print("No added or modified files the index tokenizes in the diff.")
        return 0

    all_added = added_lines(args.base, args.head)
    # Only the files Sonar tokenizes count toward new_lines.
    new_lines_map = {f: all_added.get(f, set()) for f in files}

    index = project_files(args.head, extensions)
    with tempfile.TemporaryDirectory() as workdir:
        corpus = tokenize(materialize(args.head, index, workdir))

    duplicated, blocks = find_duplicates(corpus, args.min_tokens, args.min_lines)
    # A duplication between two untouched files is pre-existing debt, not this PR's.
    blocks = [
        g for g in blocks
        if any(occ["file"] in new_lines_map
               and new_lines_map[occ["file"]] & set(range(occ["from"], occ["to"] + 1))
               for occ in g)
    ]

    new_total = sum(len(v) for v in new_lines_map.values())
    new_dup = sum(
        len(duplicated.get(p, set()) & lines) for p, lines in new_lines_map.items()
    )
    density = (100.0 * new_dup / new_total) if new_total else 0.0

    result = {
        "new_lines": new_total,
        "new_duplicated_lines": new_dup,
        "new_duplicated_lines_density": round(density, 1),
        "threshold": args.threshold,
        "gate": "OK" if density <= args.threshold else "ERROR",
        "files_changed": len(files),
        "files_indexed": len(corpus),
        "duplications": merge_blocks(blocks, new_lines_map),
    }

    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"new_lines={new_total} new_duplicated_lines={new_dup} "
              f"density={density:.1f}% (threshold {args.threshold}%) -> {result['gate']}")
        for dup in result["duplications"]:
            own = dup["new_lines_in_block"]
            mine = [f for f in dup["files"] if f in own]
            others = [f for f in dup["files"] if f not in own]
            for f in mine:
                print(f"  -> {f}:{dup['ranges'][f]}  ({own[f]} new duplicated lines)")
            for f in others:
                print(f"     clones {f}:{dup['ranges'][f]}")
            print()

    return 0 if density <= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
