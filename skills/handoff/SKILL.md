---
name: handoff
description: Writes a handoff briefing of the current session so a new window can continue after /clear without loss (the Context Guard SessionStart hook loads it automatically). Trigger on "/handoff", "handoff", "briefing for a new window", "context too large", "before clear", or when Context Guard asks for it.
---

# Handoff briefing for a new window

Goal: the new window continues without follow-up questions, with a fraction of the context. The briefing replaces the
conversation, not the repo: what is in git, README, spec or memory gets linked, not copied.

## Steps

1. Get the target file (the same place the SessionStart hook reads from):
   `python ~/.claude/hooks/context_guard.py --path`
2. Write the briefing to that file with the Write tool, structure below. At most about 120 lines, bullet points,
   concrete paths, commits, commands.
3. Never put secrets in it (no passwords, tokens, keys; only their names and where they live).
4. Tell the user in one line: "Briefing is at <path>. Now /clear, it is loaded automatically afterwards."

## Structure

```markdown
# Handoff <project>, <date time>

## Task
What the user wants, in their words where it matters. Bigger frame (feature, client, release).

## Decisions by the user
Approvals, rejections, constraints from the conversation (with date) that are written nowhere else.
Also: what explicitly must NOT be done.

## Status
- Done: ... (commit hash, branch, pushed/deployed yes/no)
- In progress: ... (which file, what is missing, are tests green)
- Open: ... (next steps in order)

## Running things
Background processes, scheduled tasks, deploy loops, waiting agents/sessions, external outages, worktrees.
What the new window has to check or stop.

## Open questions for the user
Only real, still unanswered questions.

## Important places
Specs, plans, scripts, logs, dashboards (paths/URLs). Things already in README/memory: link only.

## Pitfalls
What went wrong or nearly went wrong in this session and could happen again.

## Next step
One sentence: what the new window starts with.
```

## Notes

- Called by Context Guard: finish the current task cleanly first (nothing half changed), then write the briefing.
  In the middle of a change, write no briefing; tell the user it comes once the change is done.
- A briefing of this session from today already exists: write a new file (the hook takes the newest).
- Right after a fresh /clear there is nothing to hand over: do not write an empty briefing, it would hide the last real one.
