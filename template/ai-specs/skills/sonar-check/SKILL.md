---
name: sonar-check
description: Predict the SonarQube Cloud quality-gate verdict for the current diff or a PR, before pushing. Use it when the user asks to check or anticipate Sonar, asks whether the gate will pass, or wants duplication, code smells or security hotspots on new code reviewed.
compatibility: Requires git, python3 (standard library only) and, for PHP, the php CLI. Reading the real gate needs a SonarCloud token in $SONAR_TOKEN or ~/.config/sonar/token.
metadata:
  author: moova
  version: "1.0"
---

SonarQube Cloud analyzes every PR and posts its verdict as a GitHub check. This skill
**anticipates that verdict locally**, on the same new code Sonar looks at, so you don't find
out after pushing.

The goal is to predict the verdict and explain why — not a general code review. For bugs, use
`/code-review`; this is specifically the gate.

Scripts live in `ai-specs/skills/sonar-check/scripts/`:

| Script | What it does |
|---|---|
| `duplication.py` | Measures `new_duplicated_lines_density` locally, indexing the whole project like Sonar does |
| `sonar.py` | Read-only SonarCloud API: `gate`, `issues`, `hotspots`, `prs`, `history`, `whoami` |

## Repo configuration

All optional. The skill works with none of it, and gets sharper with each piece.

**1. A "Sonar" note in `CLAUDE.md` / `AGENTS.md`** — only for what can't be derived:

```markdown
## Sonar
- project: `myorg_my-repo`
- organization: `myorg`
- duplication: `--min-tokens 95 --min-lines 10 --langs php,groovy`
```

- `project` / `organization`: pass them to `sonar.py` as `--project` / `--org`. Without the note,
  `sonar.py` reads `sonar-project.properties`, then falls back to SonarCloud's default for a
  GitHub-imported project (`<owner>` and `<owner>_<repo>` from the `origin` remote). Run
  `sonar.py whoami` to see what it resolved.
- `duplication`: extra flags for `duplication.py`, exactly as calibrated for this repo. Without
  it the defaults apply (`--min-tokens 95 --min-lines 10 --langs php,groovy,js,sql`).

**2. The repo's own evidence, in `ai-specs/sonar/`** — files the repo owns (the toolkit never
writes or updates them):

- `ai-specs/sonar/rules.md` — the rules that *actually* fire in this repo, by real frequency,
  what triggers them here, what is deliberate and must not be "fixed", and the repo's known
  duplication hotspots. Read it in place of — or on top of — the generic `rules.md` next to
  this file.
- `ai-specs/sonar/calibration.md` — the PRs `duplication.py` was checked against (real vs.
  estimated density), the parameters chosen, and what was learned. This is what lets you say
  how much to trust the duplication number.

If they don't exist, use the generic catalog and, at the end of the report, **offer** to build
them from the repo's history (see "Building the repo's evidence"). Never create them unasked.

## The gate to predict

Read the real conditions once from any analyzed PR (`sonar.py prs`, then `sonar.py gate <pr>`).
The default "Sonar way" for new code is:

| Condition | Threshold | How it's evaluated here |
|---|---|---|
| `new_duplicated_lines_density` | ≤ 3% | `duplication.py`, measured |
| `new_security_rating` | A (zero new vulnerabilities) | judgment, from the diff |
| `new_security_hotspots_reviewed` | 100% | judgment, from the diff |
| `new_reliability_rating` | A (zero new bugs) | judgment, from the diff |
| `new_maintainability_rating` | A | code smells; one new smell barely moves it |

If the project's gate has a coverage condition, say so — but if it doesn't, **don't report
coverage as a gate risk**. Duplication is, by a wide margin, what fails gates in practice; order
the report accordingly unless the repo's `rules.md` says otherwise.

## Procedure

### 1. Resolve the range

Sonar compares against the PR's base, so use the same base.

- **With a PR number** (`/sonar-check 123`):
  ```bash
  read -r base head < <(gh api "repos/{owner}/{repo}/pulls/<PR>" --jq '[.base.sha,.head.sha]|@tsv')
  git cat-file -e "$head" 2>/dev/null || git fetch origin "refs/pull/<PR>/head"
  ```
- **Without an argument**, on what you're working on: the base is the merge-base against the
  branch the PR targets (or will target), and the head is the working tree.
  ```bash
  target=$(gh pr view --json baseRefName --jq .baseRefName 2>/dev/null)   # existing PR
  base=$(git merge-base "origin/${target:-<default branch>}" HEAD)
  ```
  With no PR yet, the target is the repo's default branch unless its `CLAUDE.md` / `AGENTS.md`
  says PRs go elsewhere. If the branch was cut from a different branch than the one the PR
  targets, the diff fills with unrelated changes — check that `git diff --stat "$base"` looks
  like this branch's work before measuring.

If the diff is empty, say so and stop.

### 2. Measure duplication

```bash
python3 ai-specs/skills/sonar-check/scripts/duplication.py --base "$base" [--head "$head"] [<flags from the Sonar note>] --json
```

It returns the density and each duplicated block with file and line range, telling the diff's
own lines apart from the code they clone. It indexes the whole project, as Sonar does — a new
file that clones an untouched one still counts.

- **Commit new files before measuring**, or measure with `--head` on a commit. Files only
  staged with `git add -N` are left out of the index: their lines count toward the total but
  have nothing to match against, so the density comes out low. Check that `files_indexed`
  includes them.
- **Don't tweak thresholds** to "improve" a single result. Parameters change only with
  calibration evidence (see below).

### 3. Review the diff against the catalog

Read the repo's `ai-specs/sonar/rules.md` if it exists, and the generic `rules.md` next to this
file. Then read the diff and look for those rules, in this priority:

1. **New bugs and vulnerabilities** — either one fails the gate.
2. **Security hotspots** — the gate requires all of them reviewed, so a new one fails it until
   someone marks it in Sonar.
3. **Code smells** — informational. Don't inflate them: they're noise if the gate passes anyway.

### 4. Report in the shape of the gate

Open with the predicted verdict and the condition that decides it. Then:

- **Duplication**: the percentage, and for each block the files and ranges. Duplication is
  often deliberate (a quick fix, not touching critical code, a ticket for the debt later) — don't
  present it as an error to fix: show the blocks and ask whether it's intentional. If it is,
  offer to draft the note for a tech-debt ticket.
- **Bugs / vulnerabilities / hotspots**: one by one, with file, line and the fix.
- **Code smells**: grouped by rule, **separating tests from production code** — Sonar analyzes
  tests like any other code, and the two rarely deserve the same decision.
- Flag explicitly what is deliberate and should be left alone (the repo's `rules.md` lists
  these).

Don't propose fixing everything. Separate what fails the gate from debt worth noting.

Be honest about certainty: duplication is **measured**; bugs, vulnerabilities and smells come
from reading the diff, so there can be false negatives. Never say "the gate will pass" with more
confidence than that.

### 5. After pushing, check against the real gate

Once Sonar has analyzed the PR:

```bash
python3 ai-specs/skills/sonar-check/scripts/sonar.py gate <PR>     # conditions and real status
python3 ai-specs/skills/sonar-check/scripts/sonar.py issues <PR>   # issues on new code
```

If the prediction missed, that is data: offer to record the case in
`ai-specs/sonar/calibration.md`. The detector is corrected with evidence, not by eye.

## Building the repo's evidence

Only when the user agrees. Both files come from the same command:

```bash
python3 ai-specs/skills/sonar-check/scripts/sonar.py history --last 60 [--json]
```

It reports, over the last N analyzed PRs: how many times the gate failed and on which condition,
every rule that fired on new code (with count, type, severity and how many were in tests), and,
per PR, the **real** `new_duplicated_lines_density`.

- **`rules.md`**: start with what failed the gate and how often, then the rules by frequency.
  For each frequent rule, read a couple of the flagged lines to say *what triggers it in this
  repo* and whether it's deliberate. Add the duplication hotspots you find while calibrating.
- **`calibration.md`**: for each PR in the history with a real density, run `duplication.py`
  on its base and head (step 1 shows how to get them) and tabulate real vs. estimated and
  whether the pass/fail verdict matches. Include PRs on both sides of the threshold. If the
  verdict misses often, move `--min-tokens` in steps of 5 and add `--langs` groups Sonar
  analyzes in this repo (a `Jenkinsfile` counts as Groovy, and `.sql` files — migrations, audit scripts — as PL/SQL; a `plsql:` or `groovy:` rule in the history is the tell); prioritize matching
  pass/fail over matching the percentage. Record the chosen flags in the "Sonar" note.

## Limits worth knowing

- An **organization token** reaches the gate, issues and the PR list, but not `measures/*`,
  `duplications/*` or `hotspots/*` (they answer "Project doesn't exist" or 404). That's why
  duplication is measured locally, and why `sonar.py hotspots` may need a user token.
- Project exclusions live in the SonarCloud UI and the token can't read them, so the local
  index may include files Sonar ignores.
- Only PHP has a real tokenizer (`token_get_all`). Every other language uses a generic one, so
  its numbers are approximate until the repo's calibration says otherwise.
