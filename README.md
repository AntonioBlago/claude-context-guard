# Context Guard for Claude Code

Long Claude Code sessions get expensive and slow, because every call re-sends the whole conversation. In my own
sessions, cache reads of the existing context were more than 95 % of all tokens (measured October 2026).

Context Guard is one Python file (stdlib only) plus one skill:

- **Warns at the right moment.** From 300k tokens of context (then every further 100k), Claude finishes the current
  step, writes a handoff briefing and tells you to `/clear`.
- **Carries the briefing over.** After `/clear`, a SessionStart hook injects the newest briefing of the project, so
  the new window continues where the old one stopped, with a fraction of the context.
- **Flags a bloated CLAUDE.md** (over 40 KB), which is loaded on every start.

No dependencies, no network, no telemetry. A hook that fails stays silent and never blocks Claude Code.

## Install

1. Copy the files:

   ```bash
   mkdir -p ~/.claude/hooks ~/.claude/skills/handoff
   cp context_guard.py ~/.claude/hooks/
   cp skills/handoff/SKILL.md ~/.claude/skills/handoff/
   ```

2. Add the hooks to `~/.claude/settings.json` (merge with existing `hooks`; on Windows use the full path, e.g.
   `C:/Users/<you>/.claude/hooks/context_guard.py`, and `python` instead of `python3`):

   ```json
   {
     "hooks": {
       "SessionStart": [
         { "hooks": [ { "type": "command", "command": "python3 ~/.claude/hooks/context_guard.py --start", "timeout": 15 } ] }
       ],
       "UserPromptSubmit": [
         { "hooks": [ { "type": "command", "command": "python3 ~/.claude/hooks/context_guard.py --prompt", "timeout": 15 } ] }
       ]
     }
   }
   ```

3. Restart Claude Code. Type `/handoff` any time to write a briefing manually.

Requires Python 3.8+.

## How it works

| Event | What happens |
|---|---|
| `UserPromptSubmit` | Reads the token usage of the last main call from the session transcript (subagents excluded). Above the threshold, once per level, it shows you a notice and tells Claude to write a briefing after the current step. |
| Skill `handoff` | Claude writes the briefing (task, your decisions, status, running things, open questions, pitfalls, next step) to `~/.claude/handoffs/<project>/<YYYY-MM-DD_HHMM>.md`. |
| `SessionStart` (after `/clear` or startup) | Injects the newest briefing of the current project if it is younger than 48 h and not loaded yet. Briefings over ~9,000 characters are passed as a read instruction instead, because Claude Code truncates large hook output. |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `CONTEXT_GUARD_WARN` | `300000` | First warning at this many context tokens |
| `CONTEXT_GUARD_STEP` | `100000` | Warn again every this many tokens |
| `CONTEXT_GUARD_MAX_AGE_H` | `48` | Ignore older briefings |

Set them in the `env` block of `settings.json`. With a 200k context window, use e.g. `CONTEXT_GUARD_WARN=120000`.

## Tests

```bash
python -m pytest test_context_guard.py
```

## Deutsch

Context Guard meldet sich, wenn eine Claude-Code-Sitzung zu groß wird, lässt Claude ein Übergabe-Briefing schreiben
und lädt es nach `/clear` automatisch ins neue Fenster. Installation wie oben. Die Meldungen sind auf Englisch;
Claude antwortet trotzdem in deiner Sprache.

## More skills

Context Guard is part of how I work with Claude Code every day. The **Vibe Coding Set** bundles the guardrails and
security skills for building and shipping your own tools with an AI agent (German):
[antonioblago.com/de/skills/vibe-coding/](https://www.antonioblago.com/de/skills/vibe-coding/?utm_source=github&utm_medium=readme&utm_campaign=context-guard)

All sets: [antonioblago.com/de/skills/](https://www.antonioblago.com/de/skills/?utm_source=github&utm_medium=readme&utm_campaign=context-guard)

## License

MIT, see [LICENSE](LICENSE). By [Antonio Blago](https://www.antonioblago.com).
