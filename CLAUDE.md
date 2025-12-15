# Project Configuration

## Session Continuity (CRITICAL - READ FIRST)

**On session start:**
1. Read `.claude/state.md` to understand current work state
2. If state references complex decisions or you need historical context, query graphiti-memory with `search_facts` or `get_episodes`
3. Confirm your understanding before proceeding

**Before session end (or when user types /handoff):**
1. Update `.claude/state.md` with current progress, blockers, and next steps
2. For significant decisions, architectural changes, or failed approaches, store an episode in graphiti-memory using `add_episode`
3. Summarize handoff state to the user

## What Goes Where

| Information Type | Storage Location |
|------------------|------------------|
| Current task & immediate next steps | `.claude/state.md` |
| What's been completed this session | `.claude/state.md` |
| Architectural decisions with rationale | graphiti-memory |
| Failed approaches (so we don't retry) | graphiti-memory |
| External dependencies & blockers | `.claude/state.md` |
| Long-running context (multi-week) | graphiti-memory |

## Graphiti Memory Guidelines

When using `add_episode`, structure entries clearly:
- Include date and task context
- Be specific about what was decided and why
- For failed approaches, note what went wrong

When querying, prefer:
- `get_episodes` for recent session context
- `search_facts` for specific decisions or relationships
- `search_nodes` for understanding entities in the project

## Project Conventions

<!-- Add your project-specific conventions below -->
