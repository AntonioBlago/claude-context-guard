"""Context Guard for Claude Code: tells you when a /clear pays off and carries a handoff briefing into the new window.

Hooks (~/.claude/settings.json, see README):
- UserPromptSubmit:  python context_guard.py --prompt
  Reads the current context size from the session transcript. From WARN_TOKENS on (and every STEP_TOKENS after that),
  once per level: a visible notice for you and an instruction for Claude to finish the current task, write a briefing
  with the skill /handoff and recommend /clear.
- SessionStart:      python context_guard.py --start
  After /clear (and on startup if the briefing is fresh): injects the newest, not yet loaded briefing of the project.
- Skill handoff:     python context_guard.py --path
  Prints the file the briefing should be written to.

Briefings: ~/.claude/handoffs/<project-slug>/<YYYY-MM-DD_HHMM>.md
Why: every call re-sends the whole conversation; in long sessions cache reads are by far the largest share of tokens.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path.home()
HANDOFFS = HOME / ".claude" / "handoffs"
STATE = HOME / ".claude" / "context_guard"
WARN_TOKENS = int(os.environ.get("CONTEXT_GUARD_WARN", "300000"))
STEP_TOKENS = int(os.environ.get("CONTEXT_GUARD_STEP", "100000"))
BRIEFING_MAX_AGE_H = int(os.environ.get("CONTEXT_GUARD_MAX_AGE_H", "48"))
INLINE_MAX_CHARS = 9000  # Claude Code moves hook output above ~10,000 characters into a file
CLAUDE_MD_MAX = 40_000  # above this, CLAUDE.md costs noticeable tokens on every start


def slug(cwd: str) -> str:
    """Project folder name the way Claude Code builds it (c:\\Users\\me\\x -> c--users-me-x), lowercased."""
    return re.sub(r"[:\\/. ]", "-", cwd).lower()


def context_tokens(transcript: str) -> int | None:
    """Context size of the last main call (no subagents): input + cache read + cache write."""
    try:
        with open(transcript, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 3_000_000))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("isSidechain") or e.get("type") != "assistant":
            continue
        u = (e.get("message") or {}).get("usage") or {}
        if u:
            return (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + \
                (u.get("cache_creation_input_tokens") or 0)
    return None


def on_prompt(hook: dict) -> dict | None:
    tokens = context_tokens(hook.get("transcript_path") or "")
    if not tokens or tokens < WARN_TOKENS:
        return None
    level = WARN_TOKENS + (tokens - WARN_TOKENS) // STEP_TOKENS * STEP_TOKENS
    STATE.mkdir(parents=True, exist_ok=True)
    state_file = STATE / f"{hook.get('session_id', 'unknown')}.json"
    try:
        last = json.loads(state_file.read_text(encoding="utf-8")).get("level", 0)
    except (OSError, ValueError):
        last = 0
    if level <= last:
        return None  # already reported for this level
    state_file.write_text(json.dumps({"level": level, "at": time.time()}), encoding="utf-8")
    k = round(tokens / 1000)
    return {
        "systemMessage": f"Context of this session: ~{k}k tokens, re-sent with every call. "
                         "After the next finished step: write a briefing (/handoff) and /clear.",
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                f"Context Guard: this session has ~{k}k tokens of context. Handle the user's current message first. "
                "When the running task is at a clean point afterwards (nothing half changed, no open question), run "
                "the skill `handoff` (briefing for the new window) and end your answer with one line: \"/clear, the "
                "briefing is loaded automatically afterwards.\" If the task is still in progress, only mention "
                "briefly that a /clear is due once it is done."),
        },
    }


def on_start(hook: dict) -> str | None:
    source = hook.get("source", "")
    if source not in ("clear", "startup"):
        return None  # resume/compact: the context is still there
    folder = HANDOFFS / slug(hook.get("cwd") or os.getcwd())
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    latest = files[0]
    age_h = (time.time() - latest.stat().st_mtime) / 3600
    done = folder / ".loaded"
    taken = done.read_text(encoding="utf-8").splitlines() if done.exists() else []
    if age_h > BRIEFING_MAX_AGE_H or (source == "startup" and latest.name in taken):
        return None
    with done.open("a", encoding="utf-8") as fh:
        fh.write(latest.name + "\n")
    text = latest.read_text(encoding="utf-8")
    # The VS Code extension does not show SessionStart systemMessage, only Claude's answer; hence the required line.
    head = (f"Handoff briefing from the previous session ({latest.name}, {age_h:.0f} h old, file {latest}). "
            f"Start your first answer with exactly this line: \"Handoff briefing {latest.name} loaded.\" Continue "
            f"where it says; only ask the user about what the briefing marks as open.")
    if len(text) > INLINE_MAX_CHARS:
        # Claude Code would show only a 2 KB preview of large hook output; a clear read instruction works better.
        return (f"{head}\n\nREQUIRED before your first answer: the briefing is too large for the hook "
                f"({len(text)} characters). Read the file {latest} completely with the Read tool and work with it, "
                f"even if the user's first message does not mention it.")
    return f"{head}\n\n{text}"


def claude_md_warning(cwd: str) -> str | None:
    try:
        size = (Path(cwd) / "CLAUDE.md").stat().st_size
    except OSError:
        return None
    if size <= CLAUDE_MD_MAX:
        return None
    return (f"CLAUDE.md is large ({size // 1000} KB, loaded on every start). "
            "Suggest moving detail sections into linked docs.")


def main():
    # Always UTF-8 (a Windows pipe would be cp1252, Claude Code reads UTF-8)
    sys.stdout.reconfigure(encoding="utf-8")
    if "--path" in sys.argv:
        folder = HANDOFFS / slug(os.getcwd())
        folder.mkdir(parents=True, exist_ok=True)
        print(folder / time.strftime("%Y-%m-%d_%H%M.md"))
        return
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        hook = {}
    try:
        if "--prompt" in sys.argv:
            out = on_prompt(hook)
            if out:
                print(json.dumps(out, ensure_ascii=False))
        elif "--start" in sys.argv:
            out = on_start(hook)
            big = claude_md_warning(hook.get("cwd") or os.getcwd())
            if big and not out:
                print(json.dumps({"systemMessage": big, "hookSpecificOutput": {
                    "hookEventName": "SessionStart", "additionalContext": big}}, ensure_ascii=False))
            elif big:
                out = f"{out}\n\n{big}"
            if out:
                # Plain text only reaches Claude; systemMessage shows the user that the briefing was loaded.
                name = re.search(r"\((\d{4}-\d{2}-\d{2}_\d{4}\.md)", out)
                print(json.dumps({
                    "systemMessage": f"Handoff briefing loaded: {name.group(1) if name else 'newest briefing'}",
                    "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": out},
                }, ensure_ascii=False))
    except Exception:
        pass  # a hook must never block


if __name__ == "__main__":
    main()
