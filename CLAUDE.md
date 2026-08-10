# Project Configuration

## Session Continuity (CRITICAL - READ FIRST)

**Work on natKit is directed and recorded on the Vikunja board**, reached
through the `assistant` CLI (there is an `assistant` skill; run `assistant
health` if unsure it is up). natKit is **project 53**, and tickets carry the
identifier form `TEC-NATKIT-<n>` as well as a numeric id.

**On session start:**
1. Read `.claude/state.md` to understand current work state.
2. Check the board: `assistant tasks -project 53 -recursive`. Find the ticket
   the request maps to before starting, and read it with `assistant task <id>`
   — **the list view omits descriptions, labels and percent-done**, so the list
   alone will mislead you.
3. Confirm your understanding before proceeding.

**While working — record on the ticket, not only in chat:**
- Comment findings as you go (`assistant task comment <id> -`), especially
  anything that *contradicts* the ticket, or that a future session would
  otherwise have to rediscover. Bodies are markdown (converted since assistant
  v0.7.0).
- Attach UI verification screenshots with `assistant task attach <id> <path>...`
  (`-if-absent` makes re-runs safe).
- Prefer `task comment` over rewriting a description a human wrote; use
  `-append-description` if you must add to one. `-dry-run` before bulk edits.
- If the work turns out to be several tickets, split it; file what you find
  missing rather than burying it in a comment.

**Before session end (or when the user types /handoff):**
1. Update `.claude/state.md` with current progress, blockers, and next steps.
2. Update the tickets you moved — status, percent, and **the commit sha**.
3. Summarize handoff state to the user.

## What Goes Where

| Information Type | Storage Location |
|------------------|------------------|
| What work exists, its status, and the evidence for it | Vikunja project 53 |
| Current task & immediate next steps | `.claude/state.md` |
| What's been completed this session | `.claude/state.md` |
| External dependencies & blockers | `.claude/state.md` |
| Decisions, gotchas and traps worth remembering for months | auto-memory (`MEMORY.md` + files beside it) |
| Long-running plans with rationale | `plans/*.html`, linked from the ticket |

Rule of thumb: **if it is about a piece of work, it belongs on the ticket**; if
it is a fact about the codebase or environment that will outlive the work, it
belongs in auto-memory.

## Graphiti Memory (currently unavailable)

Earlier revisions of this file routed decisions to `graphiti-memory`. That MCP
server has not been connected in recent sessions, so **do not rely on it** — use
the board and auto-memory as above. If it is reconnected, `add_episode` is still
a reasonable home for architectural decisions and failed approaches; prefer
`get_episodes` for recent context and `search_facts` for specific decisions.

## Project Conventions

<!-- Add your project-specific conventions below -->
