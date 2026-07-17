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

## Creating a ticket (Atlassian MCP)

Used by `/ticket` to create a new issue after the user approves the draft.

- Load the create tools with **ToolSearch**:
  `select:mcp__claude_ai_Atlassian_Rovo__createJiraIssue,mcp__claude_ai_Atlassian_Rovo__searchJiraIssuesUsingJql,mcp__claude_ai_Atlassian_Rovo__atlassianUserInfo`.
  Same auth flow as reading (if a call fails asking for auth, tell the user to run `/mcp` → "claude.ai Atlassian Rovo").
- Resolve `cloudId` as in "Reading a ticket".
- **Project key, issue type, and title prefix are repo conventions** — take them from the consumer's
  `CLAUDE.md` / `AGENTS.md`; if absent, ask the user (AskUserQuestion). Default issue type: `Story`.
- **Assignee**: the current user — get the accountId from `atlassianUserInfo`.
- **Active sprint** (optional; do NOT hard-code the sprint number — it changes): on Moova's instance the
  sprint field is `customfield_10020`. Resolve the current sprint id by querying an issue already in the
  open sprint:
  ```
  searchJiraIssuesUsingJql(jql: "project = <KEY> AND sprint IN openSprints() ORDER BY created DESC",
    fields: ["customfield_10020"], maxResults: 1)
  ```
  Read `customfield_10020` from the result, pick the entry whose `state` is `active`, and use its `id`.
  If there is no open sprint, ask the user whether to create the ticket in the backlog instead.
- Create with `createJiraIssue`: `cloudId`, `projectKey`, `issueTypeName`, `summary` (with the repo's
  title prefix), `contentFormat: "markdown"`, `description` (the approved text), `assignee_account_id`,
  and `additional_fields: { "customfield_10020": <activeSprintId> }` (omit if backlog).
- Report the created key + URL (e.g. `https://moova1.atlassian.net/browse/<KEY>-XXXX`).

## Fallback

- If the ticket system is unreachable, ask the user to paste the ticket content instead of guessing.
- When creating (`/ticket`), if the MCP is unavailable, present the finished ticket as Markdown for the
  user to paste into Jira by hand.
