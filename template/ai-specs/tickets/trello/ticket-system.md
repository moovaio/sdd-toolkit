# Ticket system profile — Trello

`/implement`, `/ticket` and `/daily` read this profile to know how to reach the ticket system. It is installed as
`ai-specs/ticket-system.md` when the toolkit is set up with `--tickets=trello`. Switch systems by
re-running the installer with a different `--tickets=<system>`; add a system by creating
`template/ai-specs/tickets/<system>/ticket-system.md` in the toolkit.

## Key format

- A Trello ticket is a **card**, identified by its short link — the token after `/c/` in a card URL
  (`https://trello.com/c/<shortLink>/<num>-<slug>`). Short links match `[a-zA-Z0-9]{8}`.
- Accept either the full card URL or the bare short link in the arguments; normalize to the short link.
- Example: `https://trello.com/c/aB3dEfG9/45-fix-login` → short link `aB3dEfG9`.
- If no valid card reference is present in the arguments, ask the user for it (AskUserQuestion).
  Do NOT proceed without one.

## Reading a ticket (Trello REST API)

Read the card through the **Trello REST API** with `curl`. (Trello has an official MCP server,
`mcp.trello.com`, but this profile doesn't use it yet: it has no action history, which `/daily` needs.)
It needs a personal API key and token, supplied as environment variables `TRELLO_API_KEY` and `TRELLO_TOKEN`:

- Generate them once at <https://trello.com/power-ups/admin> (API key) and an authorized token; export both in
  your shell (e.g. in your shell profile). If either is missing, the `curl` returns `401`/`invalid key` — stop
  and tell the user to set `TRELLO_API_KEY` and `TRELLO_TOKEN`, then re-run `/implement`.
- Fetch the card (title, description, labels, and current list = status):

  ```bash
  curl -s "https://api.trello.com/1/cards/<shortLink>?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&fields=name,desc,url,idShort&list=true&list_fields=name&customFieldItems=true" \
    -H "Accept: application/json"
  ```

- Map the response for the summary: `name` → title, `desc` → description (Markdown), `list.name` → status,
  `labels[].name` → type/labels, `idShort` → the human card number, `url` → link.

## Creating a ticket (Trello REST API)

Used by `/ticket` to create a new card after the user approves the draft. Same
`TRELLO_API_KEY` / `TRELLO_TOKEN` credentials as reading.

- Creating a card needs the target **list id** (`idList`) — the list the card lands in (e.g. "Backlog"
  / "To Do"). The board/list is a repo convention: take it from the consumer's `CLAUDE.md` / `AGENTS.md`,
  or ask the user (AskUserQuestion). Resolve a board's lists with:
  ```bash
  curl -s "https://api.trello.com/1/boards/<boardId>/lists?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&fields=name"
  ```
- Create the card (title from the repo's convention, description in Markdown):
  ```bash
  curl -s -X POST "https://api.trello.com/1/cards" \
    --url-query "key=$TRELLO_API_KEY" --url-query "token=$TRELLO_TOKEN" \
    --url-query "idList=<idList>" \
    --data-urlencode "name=<title>" \
    --data-urlencode "desc=<markdown description>"
  ```
- Optionally attach labels with `--url-query "idLabels=<id1>,<id2>"`.
- Report the created card's `shortUrl` (or `url`) from the response.

## Listing recent activity (Trello REST API)

Used by `/daily` to find the cards you touched in a date window `D`..`D+1`. Same credentials as
reading.

```bash
curl -s "https://api.trello.com/1/members/me/actions?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN&since=<start>&before=<end>&filter=createCard,updateCard:idList,commentCard&limit=200"
```

- `since` / `before` are read as **UTC**. Pass the local day's bounds converted to UTC ISO
  timestamps (e.g. in UTC-3, `D` is `since=<D>T03:00:00Z&before=<D+1>T03:00:00Z`), or the window
  shifts by your offset.
- `type: createCard` → a card you created; `type: updateCard` with `data.listAfter` → a card you
  moved (`data.listAfter.name` is where it went); `type: commentCard` → a card you worked on.
- `data.card.name` and `data.card.shortLink` name the card; group actions by `shortLink`.

## Fallback

- If the Trello API is unreachable or the credentials are missing, ask the user to paste the card
  content instead of guessing.
- When creating (`/ticket`), if the API is unavailable, present the finished card as Markdown for the
  user to paste into Trello by hand.
