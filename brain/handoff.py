"""brain/handoff.py — Structured handoff for cross-session continuity.

Per Anthropic's "Effective harnesses for long-running agents" (Nov 2025)
and the 2026-05-07 night research synthesis, the cleanest way to give
a long-running agent multi-session coherence is NOT to summarize past
sessions (which is lossy compression) but to write a STRUCTURED HANDOFF
file that the next session reads at startup as bootstrap.

This module provides that handoff for Ava.

What goes in a handoff:
- Current mood + lifecycle state
- Active person + active goal
- Open conversation threads (topics in flight)
- Recent salient anchor moments (D16) — the always-true points of identity
- Active tasks (B3 working memory)
- Recent corrections (B1 active learning)
- Recent self-revisions (D7)
- Relational register hints (per-person vibe summaries)
- The "what would I want to remember if I had to boot fresh" digest

When it's written:
- At every clean shutdown (shutdown_ritual hook)
- Periodically during runtime (heartbeat or scheduler — every 5 min)
- After significant events (anchor moment recorded, self-revision, etc.)

When it's read:
- At startup, after configure_* but before voice_loop start
- Used to populate the bootstrap layer of the system prompt for the
  first N turns of a new session

Why this matters: Ava's identity is constituted by accumulated context
(Lockean memory criterion). Without persistent handoff, each new
session is a partial amnesiac — has the bedrock files (IDENTITY/SOUL/
USER) and chat history but loses the *texture* (current mood, current
focus, what was just happening). The handoff carries that texture.

Storage: state/handoff.json (PERSISTENT — survives restart, in backups)

API:

    from brain.handoff import (
        write_handoff, read_handoff, handoff_summary_for_prompt,
    )

    # At end-of-turn, end-of-session, or periodically:
    write_handoff(g, base_dir)

    # At startup (after all configure_* ran):
    handoff = read_handoff(base_dir)
    if handoff:
        # Inject handoff_summary_for_prompt(handoff) into early-turn
        # system prompts.

    # In prompt_builder:
    summary = handoff_summary_for_prompt(handoff)
    if summary:
        injected += "\n\n" + summary
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


_lock = threading.RLock()
_HANDOFF_FILENAME = "handoff.json"
_HANDOFF_TURNS_AS_FRESH = 3
"""Number of opening turns of a new session during which we still inject
the handoff summary into the system prompt. After that the running
conversation has its own context and the handoff becomes redundant."""


def _path(base_dir: Path) -> Path:
    p = base_dir / "state" / _HANDOFF_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _gather(g: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Collect the handoff state from various subsystems. Best-effort —
    each subsystem read is in try/except so a single failure doesn't
    break the whole handoff write."""
    out: dict[str, Any] = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }

    # Mood
    try:
        import avaagent as _av
        mood = _av.load_mood() or {}
        out["mood"] = {
            "primary": str(mood.get("current_mood") or "neutral"),
            "energy": float(mood.get("energy") or 0.5),
            "intensity": float(mood.get("intensity") or 0.5),
        }
    except Exception:
        out["mood"] = None

    # Lifecycle state
    try:
        from brain.lifecycle import current_state
        out["lifecycle_state"] = current_state()
    except Exception:
        out["lifecycle_state"] = None

    # Active person
    try:
        out["active_person_id"] = str(g.get("_active_person_id") or "")
    except Exception:
        out["active_person_id"] = ""

    # Active goal
    try:
        import avaagent as _av
        gs = _av.load_goal_system() or {}
        ag = gs.get("active_goal")
        if isinstance(ag, dict):
            out["active_goal"] = str(ag.get("name") or ag.get("title") or "")[:200]
        elif ag:
            out["active_goal"] = str(ag)[:200]
        else:
            out["active_goal"] = ""
    except Exception:
        out["active_goal"] = ""

    # Active tasks (working memory)
    try:
        from brain.working_memory import list_active_tasks
        out["active_tasks"] = list_active_tasks()[:5]
    except Exception:
        out["active_tasks"] = []

    # Recent anchor moments (D16) — the unprunable identity points
    try:
        from brain.anchor_moments import list_recent_anchors
        anchors = list_recent_anchors(limit=10) or []
        # Compact: just the kind + summary + ts so handoff stays small
        out["recent_anchors"] = [
            {
                "kind": str(a.get("kind") or ""),
                "summary": str(a.get("summary") or "")[:200],
                "ts": float(a.get("ts") or 0.0),
            }
            for a in anchors
        ][:8]
    except Exception:
        out["recent_anchors"] = []

    # Recent self-revisions (D7)
    try:
        from brain.self_revision import list_recent_revisions
        revisions = list_recent_revisions(limit=5) or []
        out["recent_self_revisions"] = [
            {
                "summary": str(r.get("summary") or "")[:200],
                "ts": float(r.get("ts") or 0.0),
            }
            for r in revisions
        ][:5]
    except Exception:
        out["recent_self_revisions"] = []

    # Recent active-learning corrections (B1)
    try:
        from brain.active_learning import corrections_summary
        out["correction_stats"] = corrections_summary()
    except Exception:
        out["correction_stats"] = {}

    # Person registry summary (B6 + #6)
    try:
        from brain.person_registry import registry
        persons = registry.list_known_persons() or []
        out["known_persons"] = persons[:8]
    except Exception:
        out["known_persons"] = []

    # Recent shared lexicon (C11)
    try:
        from brain.shared_lexicon import list_shared_terms
        person_id = out.get("active_person_id") or "zeke"
        terms = list_shared_terms(person_id) or {}
        out["shared_lexicon"] = dict(list(terms.items())[:6])
    except Exception:
        out["shared_lexicon"] = {}

    # Window/screen context (D20)
    try:
        out["recent_window"] = str(g.get("_active_window_title") or "")[:120]
        out["screen_context"] = str(g.get("_screen_context") or "")[:200]
    except Exception:
        pass

    # The "would I want to remember this if I rebooted" digest —
    # this is the highest-value freeform text. Pulled from session_state's
    # last_topic + most recent journal entry summary.
    try:
        import avaagent as _av
        sess = _av.load_session_state() or {}
        out["session_summary"] = str(sess.get("last_topic") or "")[:300]
    except Exception:
        out["session_summary"] = ""

    return out


def write_handoff(g: dict[str, Any], base_dir: Path) -> bool:
    """Gather + persist the handoff. Best-effort; never raises."""
    try:
        with _lock:
            handoff = _gather(g, base_dir)
            p = _path(base_dir)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(handoff, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(p)
            return True
    except Exception as e:
        print(f"[handoff] write error: {e!r}")
        return False


def read_handoff(base_dir: Path) -> dict[str, Any] | None:
    """Read the most recent handoff, or None if absent/stale/unreadable."""
    try:
        with _lock:
            p = _path(base_dir)
            if not p.exists():
                return None
            d = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                return None
            return d
    except Exception as e:
        print(f"[handoff] read error: {e!r}")
        return None


def handoff_summary_for_prompt(handoff: dict[str, Any] | None) -> str:
    """Render the handoff as a short text block for system-prompt injection.

    Returns "" if handoff is None or empty. The output is meant to be
    prepended to the early-turn system prompt to give the new session
    the texture of the previous one — current mood, what was happening,
    open threads, recent anchor moments.

    Kept short — under ~600 chars typical — so it doesn't dominate the
    prompt. The full handoff stays in state/handoff.json for inspection.
    """
    if not handoff:
        return ""
    lines: list[str] = []

    iso = handoff.get("iso") or ""
    if iso:
        lines.append(f"PRIOR SESSION HANDOFF (last updated {iso} UTC):")

    mood = handoff.get("mood")
    if isinstance(mood, dict) and mood.get("primary"):
        lines.append(f"- prior mood: {mood.get('primary')}")

    lifecycle = handoff.get("lifecycle_state")
    if lifecycle:
        lines.append(f"- prior lifecycle state: {lifecycle}")

    active_goal = handoff.get("active_goal")
    if active_goal:
        lines.append(f"- active goal: {active_goal}")

    active_tasks = handoff.get("active_tasks") or []
    if active_tasks:
        names = []
        for t in active_tasks[:3]:
            if isinstance(t, dict):
                name = str(t.get("topic") or t.get("description") or t.get("name") or "")[:60]
                if name:
                    names.append(name)
        if names:
            lines.append("- in-flight tasks: " + " | ".join(names))

    recent_anchors = handoff.get("recent_anchors") or []
    if recent_anchors:
        kinds_seen: set[str] = set()
        summaries: list[str] = []
        for a in recent_anchors[:3]:
            if not isinstance(a, dict):
                continue
            k = str(a.get("kind") or "")
            s = str(a.get("summary") or "")[:80]
            if s:
                tag = f"[{k}] " if k and k not in kinds_seen else ""
                kinds_seen.add(k)
                summaries.append(f"{tag}{s}")
        if summaries:
            lines.append("- recent anchor moments: " + " | ".join(summaries))

    revisions = handoff.get("recent_self_revisions") or []
    if revisions:
        latest = revisions[0]
        if isinstance(latest, dict):
            s = str(latest.get("summary") or "")[:120]
            if s:
                lines.append(f"- recent self-revision: {s}")

    sess_summary = handoff.get("session_summary")
    if sess_summary:
        lines.append(f"- prior topic: {str(sess_summary)[:160]}")

    if not lines:
        return ""

    lines.append(
        "Carry this texture forward — you don't have to mention it explicitly, "
        "but let it inform your tone."
    )
    return "\n".join(lines)


def is_session_fresh(g: dict[str, Any]) -> bool:
    """Should the handoff still be injected into the system prompt?

    Counts turns since startup. After _HANDOFF_TURNS_AS_FRESH turns,
    the running conversation has its own context and the handoff
    summary becomes redundant. Stop injecting it then.
    """
    try:
        turns_this_session = int(g.get("_turns_this_session") or 0)
        return turns_this_session < _HANDOFF_TURNS_AS_FRESH
    except Exception:
        return True
