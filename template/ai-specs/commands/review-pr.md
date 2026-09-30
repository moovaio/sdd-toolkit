---
name: "Review a pull request"
description: Review an existing GitHub pull request with an independent reviewer — Claude's code-reviewer by default, or another AI CLI (Codex, Gemini, Cursor) if the repo configures one — then offer to post the findings on the PR.
category: Review
tags: [review, github, pr]
---

Independent review of a pull request that **already exists on GitHub** — yours or a teammate's,
whether or not it came out of `/implement`. The review criteria are always the same (the
`code-reviewer` agent's); what's configurable is **who runs them**: Claude by default, or another
AI CLI when you want a second opinion from a different model.

**Input**: the PR number or URL (`/review-pr 123`, `/review-pr https://github.com/org/repo/pull/123`).
With no argument, use the PR of the current branch (`gh pr view --json number`); if there is none,
ask for it (AskUserQuestion). An optional `--reviewer=<name>` overrides the configured reviewer for
this run only (`/review-pr 123 --reviewer=codex`).

This command is **repo-agnostic**. It reads:
- **This repo's agent instructions** (`CLAUDE.md` / `AGENTS.md`) — the "PR review" note (below) and
  the conventions the review is checked against.
- **`ai-specs/ticket-system.md`** — the ticket key format, to link the PR to its ticket and change.

It requires the **`gh` CLI**, authenticated (`gh auth status`). If it isn't, stop and tell the user
to run `! gh auth login`.

It is **read-only until you say otherwise**: nothing is posted to GitHub without an explicit yes.

---

## Step 1 — Resolve the reviewer

In order, the first one that applies:
1. `--reviewer=<name>` in `$ARGUMENTS`.
2. A "PR review" note in `CLAUDE.md` / `AGENTS.md`:
   ```markdown
   ## PR review
   - reviewer: `codex`
   ```
3. **Default: `claude`.** Don't ask, don't offer to configure — no note means Claude.

Known reviewers:

| Reviewer | How it runs |
|----------|-------------|
| `claude` | The `code-reviewer` subagent (Agent tool, `subagent_type: "code-reviewer"`) |
| `codex` | `codex exec --sandbox read-only -C <worktree> - < <prompt-file>` |
| `gemini` | `cd <worktree> && gemini -p "$(cat <prompt-file>)"` |
| `cursor` | `cd <worktree> && cursor-agent -p "$(cat <prompt-file>)" --output-format text` |

Any other value is taken as a **full shell command** that reads the prompt on stdin and prints the
report, run from the worktree (`- reviewer: \`my-cli review --read-only\``).

For anything other than `claude`, check the CLI is installed (`command -v <cli>`). If it isn't,
**say so and ask** whether to run the review with Claude instead — never switch silently. If a CLI
rejects a flag (their interfaces change), check `<cli> --help` and adapt, but **never add flags that
grant write access or auto-approve tool use**.

## Step 2 — Read the PR

```bash
gh pr view <n> --json number,title,body,url,state,isDraft,author,baseRefName,headRefName,headRefOid,files
gh pr view <n> --comments   # existing discussion, so the review doesn't repeat it
```

- If the PR is merged or closed, say so and ask whether to review it anyway.
- Look for a ticket key (format from `ai-specs/ticket-system.md`) in the branch name, title or body.
  If there is one, check `openspec/changes/` on the PR's head for a change whose name includes it:
  that change holds the **approved artifacts** the code should conform to. No key or no change is
  fine — then the PR description (and the ticket, if there's a key) is the statement of intent.
- Show a one-line summary (number, title, author, base ← head, files changed) and the reviewer
  that will run, then continue — this step needs no confirmation.

## Step 3 — Check out the PR head in a throwaway worktree

Review the real code at the PR's head without touching the user's working tree or branch:

```bash
git fetch origin <baseRefName> "pull/<n>/head"
WT=$(mktemp -d)/pr-<n>
git worktree add --detach "$WT" FETCH_HEAD
```

(`pull/<n>/head` works for PRs from forks too.) Check that `git -C "$WT" rev-parse HEAD` equals
`headRefOid`; if not, the PR moved — fetch again. The diff under review is
`git -C "$WT" diff --merge-base origin/<baseRefName> HEAD`.

## Step 4 — Run the review

The reviewer gets the same context whoever it is: the PR (number, URL, title, body), the base ref
(`origin/<baseRefName>`), the worktree path, the ticket key and change path if Step 2 found them,
and a digest of points already raised in the existing discussion — so it doesn't repeat them.

- **`claude`**: launch the `code-reviewer` subagent with that context. It runs in a fresh context
  and is read-only.
- **Any other reviewer**: write a prompt file in the scratchpad (or `mktemp`) made of the body of
  `ai-specs/agents/code-reviewer.md` (without its frontmatter) followed by the context above, plus
  the line: *"You are running in a disposable checkout. Do not modify files, run builds that write
  to the tree, or access the network. Your final message is the report."* Run the CLI per Step 1
  from the worktree. If it fails or times out, show its error and ask whether to retry or fall
  back to Claude.

## Step 5 — Present the report

- Show the findings ordered by severity, the verdict, and **which reviewer produced them**.
- For an external reviewer, spot-check what's cheap to check: a finding that cites a file or line
  that doesn't exist in the diff gets marked *unverified*. Don't drop findings and don't rewrite
  their substance — the point of another model is its own opinion.
- Mark findings that duplicate a point already raised in the PR discussion.

## Step 6 — Offer to publish, and CONFIRM

Use AskUserQuestion. Options:
- **Summary + inline comments** — one review with the summary as its body and each finding that has
  a `path:line` on the diff as an inline comment.
- **Summary only** — one review comment with the whole report.
- **Don't publish** (the report stays in the terminal).

Let the user drop individual findings before posting. Posting is **outward-facing and visible to the
whole team** — never post without this confirmation.

When publishing:
- Always post with event `COMMENT`. **Never approve or request changes** on someone's behalf, even
  if the verdict is `APPROVE` or `REJECT` — state the verdict in the text.
- Say in the body that it's an AI-assisted review and which reviewer produced it.
- Summary only:
  ```bash
  gh pr review <n> --comment --body-file <file>
  ```
- With inline comments, one review via the API (`line` is on the head side; skip `side` unless the
  comment is on a removed line, then use `"side": "LEFT"`):
  ```bash
  gh api repos/{owner}/{repo}/pulls/<n>/reviews --method POST --input <review.json>
  # review.json: {"commit_id": "<headRefOid>", "event": "COMMENT", "body": "<summary>",
  #               "comments": [{"path": "src/x.ts", "line": 42, "body": "..."}]}
  ```
  If GitHub rejects a comment's line (not part of the diff), move that finding into the summary
  body instead of failing the whole review.
- Show the URL of the posted review.

## Step 7 — Clean up

Always, including when an earlier step failed:

```bash
git worktree remove --force "$WT"
```

**Guardrails**
- Never post, approve, request changes, merge, push, or edit the PR without the Step 6 confirmation —
  and even then, only `COMMENT` reviews.
- Never check out the PR in the user's working tree; the throwaway worktree is the only checkout.
- Never switch reviewer silently — if the configured one can't run, ask.
- Never grant an external CLI write or auto-approve permissions.
- The review criteria live in `ai-specs/agents/code-reviewer.md` — don't restate or fork them here.
