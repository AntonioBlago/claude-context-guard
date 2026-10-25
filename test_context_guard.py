"""Run: python -m pytest test_context_guard.py"""
import json
import os
import time

import context_guard as cg


def _transcript(tmp_path, tokens):
    line = {"type": "assistant", "message": {"usage": {
        "input_tokens": 10, "cache_read_input_tokens": tokens - 10, "cache_creation_input_tokens": 0}}}
    side = {"type": "assistant", "isSidechain": True, "message": {"usage": {"input_tokens": 999_999}}}
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(line) + "\n" + json.dumps(side) + "\n", encoding="utf-8")
    return str(p)


def test_slug():
    assert cg.slug(r"C:\Users\me\My.Project") == "c--users-me-my-project"


def test_context_tokens_skips_subagents(tmp_path):
    assert cg.context_tokens(_transcript(tmp_path, 123_456)) == 123_456
    assert cg.context_tokens(str(tmp_path / "missing.jsonl")) is None


def test_prompt_warns_once_per_level(tmp_path, monkeypatch):
    monkeypatch.setattr(cg, "STATE", tmp_path / "state")
    low = {"transcript_path": _transcript(tmp_path, cg.WARN_TOKENS - 1), "session_id": "s"}
    assert cg.on_prompt(low) is None
    hook = {"transcript_path": _transcript(tmp_path, cg.WARN_TOKENS + 5), "session_id": "s"}
    assert "systemMessage" in cg.on_prompt(hook)
    assert cg.on_prompt(hook) is None  # same level: silent
    hook["transcript_path"] = _transcript(tmp_path, cg.WARN_TOKENS + cg.STEP_TOKENS)
    assert cg.on_prompt(hook) is not None  # next level: warns again


def test_start_loads_newest_briefing(tmp_path, monkeypatch):
    monkeypatch.setattr(cg, "HANDOFFS", tmp_path)
    cwd = str(tmp_path / "proj")
    folder = tmp_path / cg.slug(cwd)
    folder.mkdir()
    old, new = folder / "2026-01-01_0900.md", folder / "2026-01-01_1000.md"
    old.write_text("old", encoding="utf-8")
    new.write_text("new briefing", encoding="utf-8")
    os.utime(old, (time.time() - 60, time.time() - 60))
    out = cg.on_start({"source": "clear", "cwd": cwd})
    assert "new briefing" in out and new.name in out
    assert cg.on_start({"source": "startup", "cwd": cwd}) is None  # already loaded
    assert cg.on_start({"source": "resume", "cwd": cwd}) is None
    os.utime(new, (time.time() - (cg.BRIEFING_MAX_AGE_H + 1) * 3600,) * 2)
    os.utime(old, (time.time() - (cg.BRIEFING_MAX_AGE_H + 2) * 3600,) * 2)
    assert cg.on_start({"source": "clear", "cwd": cwd}) is None  # too old
