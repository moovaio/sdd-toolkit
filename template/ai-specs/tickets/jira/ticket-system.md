# Ticket system profile — Jira (Atlassian)

`/implement` reads this profile to know how to resolve and fetch a ticket. It is installed as
`ai-specs/ticket-system.md` when the toolkit is set up with `--tickets=jira`. Switch systems by
re-running the installer with a different `--tickets=<system>`; add a system by creating
`template/ai-specs/tickets/<system>/ticket-system.md` in the toolkit.

## Key format

- Ticket keys match `MOOV-\d+` (case-insensitive; normalize to upper-case).
- Example: `MOOV-5147`.
- If no valid key is present in the arguments, ask the user for it (AskUserQuestion). Do NOT proceed without one.

## Reading a ticket (Atlassian MCP)

- The Atlassian/Jira MCP tools are deferred in fresh sessions. If `getJiraIssue` is not available, load it with
  **ToolSearch**: `select:mcp__claude_ai_Atlassian_Rovo__getJiraIssue,mcp__claude_ai_Atlassian_Rovo__getAccessibleAtlassianResources`.
- If the MCP is not authenticated (the call fails asking for auth), stop and tell the user to run `/mcp` and select
  **"claude.ai Atlassian Rovo"**, then re-run `/implement`.
- Resolve the `cloudId` dynamically via `getAccessibleAtlassianResources` and pick the resource whose `url` is
  `https://moova1.atlassian.net` (Moova's site is `moova1`). Prefer this over any hardcoded value — it stays correct
  if the tenant ever changes. Only if that call fails, fall back to the known `moova1` cloudId
  `59e666bf-d9f2-4276-892e-4890b9daeb13` (verified 2026-07 against `getAccessibleAtlassianResources`).
- Fetch the issue with `getJiraIssue` (`responseContentFormat: "markdown"`, fields:
  `summary`, `description`, `status`, `issuetype`, `labels`, `comment`).

## Fallback

- If the ticket system is unreachable, ask the user to paste the ticket content instead of guessing.
