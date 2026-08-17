# Project Configuration

## Session Continuity (CRITICAL - READ FIRST)

**On session start:**
1. Read `.claude/state.md` to understand current work state
2. Confirm your understanding before proceeding

**Before session end (or when user types /handoff):**
1. Update `.claude/state.md` with current progress, blockers, and next steps
2. Summarize handoff state to the user

## What Goes Where

| Information Type | Storage Location |
|------------------|------------------|
| Current task & immediate next steps | `.claude/state.md` |
| What's been completed this session | `.claude/state.md` |
| External dependencies & blockers | `.claude/state.md` |
| Long-running plans, with rationale and phase breakdown | `plans/*.html` |

Task tracking, verification evidence and durable decision memory live in the
maintainer's personal tooling, configured globally rather than in this repo.

## Project Conventions

<!-- Add your project-specific conventions below -->
