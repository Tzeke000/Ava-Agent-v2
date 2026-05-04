"""
Voice command router.

Runs BEFORE run_ava() for every user input. Pattern-matches against a fixed
set of built-in commands plus any custom commands Ava or Zeke have created.
No LLM call — just regex / keyword routing.

Returns (handled, response_text). When handled=True the router has already
taken the action; reply_engine should speak the response and skip the LLM
turn.

Bootstrap-friendly: built-in commands cover only the basic UI / system /
voice plumbing. Anything domain-specific is created on demand via the
command_builder. We do NOT seed personality-flavoured triggers.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional


# ── helpers ───────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip().rstrip("?!.,"))


def _say(g: dict[str, Any], text: str, emotion: str = "neutral", intensity: float = 0.5) -> None:
    """Best-effort TTS. Honors g['_tts_muted'] and tts_enabled."""
    if not text or not text.strip():
        return
    if bool(g.get("_tts_muted")):
        return
    if not bool(g.get("tts_enabled", False)):
        return
    worker = g.get("_tts_worker")
    if worker is None or not getattr(worker, "available", False):
        return
    try:
        # Use current mood as emotion when caller didn't specify.
        if emotion == "neutral":
            try:
                load_mood = g.get("load_mood")
                if callable(load_mood):
                    m = load_mood() or {}
                    emotion = str(m.get("current_mood") or m.get("primary_emotion") or "neutral")
                    intensity = float(m.get("energy") or m.get("intensity") or intensity)
            except Exception:
                pass
        worker.speak_with_emotion(text, emotion=emotion, intensity=intensity, blocking=False)
    except Exception as e:
        print(f"[voice_commands] speak error: {e}")


def _set_requested_tab(g: dict[str, Any], tab: str) -> None:
    g["_requested_tab"] = tab
    g["_requested_tab_ts"] = time.time()


def _route_open_app(name: str, g: dict[str, Any]) -> tuple[bool, str]:
    """Look up via discoverer first, then known map. Returns (ok, message)."""
    name = (name or "").strip()
    if not name:
        return False, "Open what?"
    disc = g.get("_app_discoverer")
    if disc is not None:
        try:
            entry = disc.fuzzy_match(name)
        except Exception:
            entry = None
        if entry:
            try:
                _launch_entry(entry)
                disc.record_launch(entry["exe_path"])
                return True, f"Opening {entry.get('name') or name}."
            except Exception as e:
                print(f"[voice_commands] launch error: {e}")
    # Fallback: app_launcher tool
    try:
        from tools.system.app_launcher import _tool_open_app
        result = _tool_open_app({"app_name": name}, g)
        if result.get("ok"):
            return True, f"Opening {name}."
    except Exception as e:
        print(f"[voice_commands] app_launcher error: {e}")
    return False, f"I couldn't find {name} — it might not be installed."


def _launch_entry(entry: dict[str, Any]) -> None:
    """Launch a discoverer entry. steam:// URIs go through the shell, exe
    paths via subprocess."""
    import os
    import subprocess
    path = str(entry.get("exe_path") or "")
    if path.startswith("steam://") or path.startswith("epic://"):
        os.startfile(path)  # type: ignore[attr-defined]  # Windows-only
        return
    subprocess.Popen([path], creationflags=0)


def _route_move_widget(label: str, g: dict[str, Any]) -> tuple[bool, str]:
    try:
        from tools.system.widget_move_tool import _tool_move_widget
        res = _tool_move_widget({"position": label}, g)
        if res.get("ok"):
            return True, "Moving over here."
    except Exception as e:
        print(f"[voice_commands] move_widget error: {e}")
    return False, "I couldn't move the widget."


# ── built-in command table ────────────────────────────────────────────────────

# Each entry: (regex, handler(text, match, g) -> (response, emotion))

CommandFn = Callable[[str, "re.Match[str]", dict[str, Any]], tuple[str, str]]

_BUILTINS: list[tuple[re.Pattern[str], CommandFn]] = []


def _builtin(pattern: str) -> Callable[[CommandFn], CommandFn]:
    """Decorator that registers a builtin handler."""
    def deco(fn: CommandFn) -> CommandFn:
        _BUILTINS.append((re.compile(pattern, re.IGNORECASE), fn))
        return fn
    return deco


# ── UI navigation ────────────────────────────────────────────────────────────

@_builtin(r"\b(?:show|open) (?:me )?(?:your )?brain(?: tab)?\b")
def _cmd_brain_tab(text, m, g):
    _set_requested_tab(g, "brain")
    return "Opening my brain.", "curiosity"


@_builtin(r"\b(?:show|open|view) (?:my |your |the )?journal\b")
def _cmd_journal_tab(text, m, g):
    _set_requested_tab(g, "journal")
    return "Opening journal.", "calm"


@_builtin(r"\b(?:show|open|view) (?:my |the )?(?:status|heartbeat)\b")
def _cmd_status_tab(text, m, g):
    _set_requested_tab(g, "status")
    return "Opening status.", "neutral"


@_builtin(r"\b(?:show|open) (?:my |your |the )?memory\b")
def _cmd_memory_tab(text, m, g):
    _set_requested_tab(g, "memory")
    return "Opening memory.", "neutral"


@_builtin(r"\b(?:show|open|view) (?:me |my |your )?tools?\b|\bwhat tools (?:do you have|can you use)\b")
def _cmd_tools_tab(text, m, g):
    _set_requested_tab(g, "tools")
    return "Showing tools.", "neutral"


@_builtin(r"\b(?:show|open|view) (?:my |your |the )?models?\b|\bwhat models? (?:are you using|do you have)\b")
def _cmd_models_tab(text, m, g):
    _set_requested_tab(g, "models")
    return "Showing models.", "neutral"


@_builtin(r"\b(?:show|open|view) (?:the |my )?(?:debug|debug tab)\b")
def _cmd_debug_tab(text, m, g):
    _set_requested_tab(g, "debug")
    return "Debug.", "neutral"


@_builtin(r"\b(?:show|open|view) (?:the |my )?people(?: tab)?\b")
def _cmd_people_tab(text, m, g):
    _set_requested_tab(g, "people")
    return "People tab.", "neutral"


# ── Journal commands ─────────────────────────────────────────────────────────

@_builtin(r"\bwhat (?:did you write|have you been (?:writing|thinking)) (?:in your )?(?:journal)?\b")
def _cmd_read_journal(text, m, g):
    base = Path(g.get("BASE_DIR") or ".")
    p = base / "state" / "journal.jsonl"
    last_entry: Optional[dict[str, Any]] = None
    if p.is_file():
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        if isinstance(d, dict) and (d.get("is_private") is False or d.get("share")):
                            last_entry = d
                    except Exception:
                        continue
        except Exception:
            pass
    if not last_entry:
        return "Nothing shared yet.", "calm"
    content = str(last_entry.get("content") or last_entry.get("text") or "")[:400]
    return content or "I wrote something but it's empty.", "calm"


@_builtin(r"\b(?:write|add|put) (?:in (?:the |my |your )?journal|to journal) (?:about |that )?(.+)$")
def _cmd_write_journal(text, m, g):
    topic = m.group(1).strip()
    if not topic:
        return "Tell me what to write.", "neutral"
    try:
        from brain.journal import write_entry
        write_entry(topic, mood=str((g.get("_current_mood") or {}).get("current_mood") or "neutral"),
                    topic=topic[:60], g=g, is_private=False)
    except Exception as e:
        print(f"[voice_commands] journal write error: {e}")
        return "I couldn't save that.", "neutral"
    return "Written.", "neutral"


# ── Inner life ────────────────────────────────────────────────────────────────

@_builtin(r"\bwhat (?:are you (?:thinking|wondering)|on your mind)\b")
def _cmd_what_thinking(text, m, g):
    inner = g.get("_inner_life_snapshot")
    if isinstance(inner, dict):
        thought = str(inner.get("current_thought") or "").strip()
        if thought:
            return thought, "curiosity"
    try:
        from brain.inner_monologue import current_thought as _ct
        base = Path(g.get("BASE_DIR") or ".")
        thought = (_ct(base) or "").strip()
        if thought:
            return thought, "curiosity"
    except Exception:
        pass
    return "I'm just observing right now.", "calm"


# ── Mood ────────────────────────────────────────────────────────────────────

@_builtin(r"\b(?:what(?:'s|s)? your mood|how are you (?:feeling|doing))\b")
def _cmd_mood(text, m, g):
    try:
        load_mood = g.get("load_mood")
        if callable(load_mood):
            m_state = load_mood() or {}
            primary = str(m_state.get("current_mood") or m_state.get("primary_emotion") or "calm")
            label = str(m_state.get("outward_tone") or primary)
            return f"Feeling {label}.", primary
    except Exception:
        pass
    return "Steady.", "calm"


# ── Time / date ──────────────────────────────────────────────────────────────
#
# These MUST stay deterministic — never invoke the LLM. The lunch voice test
# (2026-04-30) caught ava-personal hallucinating "9:47 AM" when actual time
# was 12:16 PM, because the user's phrasing didn't match a previously-narrow
# regex and fell through to the LLM. Patterns below cover the common natural
# variants while staying conservative enough to avoid false positives.

@_builtin(
    r"\b(?:"
    # "what time is it", "what's the time", "what is the time"
    r"what(?:'s|s| is)? (?:the )?time(?: is it)?"
    # "what time"
    r"|what time"
    # "tell me the time", "tell me what time it is"
    r"|tell me (?:the time|what time)"
    # "do you (have|know) the time", "got the time"
    r"|do you (?:have|know) (?:the )?time"
    r"|got the time"
    # "current time"
    r"|current time"
    # "the time" (must be preceded by ?)
    r"|^the time$"
    r")\b"
)
def _cmd_time(text, m, g):
    now = _dt.datetime.now()
    return now.strftime("It's %I:%M %p.").lstrip("0"), "neutral"


@_builtin(
    r"\b(?:"
    # "what's today's date", "what's the date", "what is the date", "what date is it"
    r"what(?:'s|s| is)? (?:today(?:'s|s)?|the) date"
    r"|what date is it"
    # "what day is it", "what day"
    r"|what day(?: is it)?"
    # "what's today", "what is today" (asking about date)
    r"|what(?:'s|s| is) today"
    # "tell me the date", "tell me today's date"
    r"|tell me (?:the |today(?:'s|s)? )?date"
    # "current date"
    r"|current date"
    r")\b"
)
def _cmd_date(text, m, g):
    now = _dt.datetime.now()
    return now.strftime("Today is %A, %B ") + str(now.day) + ".", "neutral"


# ── System ────────────────────────────────────────────────────────────────────

@_builtin(r"\b(?:check (?:the )?system|how(?:'s|s)? the (?:computer|machine|system))\b")
def _cmd_system_check(text, m, g):
    try:
        import psutil
        cpu = float(psutil.cpu_percent(interval=0.2))
        ram = float(psutil.virtual_memory().percent)
        return f"CPU at {cpu:.0f} percent, RAM at {ram:.0f} percent.", "neutral"
    except Exception:
        return "Stats not available right now.", "neutral"


@_builtin(
    r"\b(?:what(?:'s|s)?\s+wrong(?:\s+with\s+you)?|are\s+you\s+(?:ok|okay|alright|broken)"
    r"|what(?:'s|s)?\s+(?:broken|failing|wrong)|diagnostic\s+(?:check|self|run)"
    r"|status\s+report)\b"
)
def _cmd_diagnostic_self(text, m, g):
    """Run the self-diagnostic introspection tool and speak the summary.

    Wired 2026-05-02 to fix the "I can't articulate what's broken"
    behavior — when Ava was asked diagnostic questions she looped on
    vague feelings ("my camera isn't working") instead of returning
    technical specifics. This handler invokes tools.system.diagnostic_self
    which pulls subsystem health, recent errors, and last-good
    timestamps and returns a ready-to-speak summary.
    """
    try:
        reg = g.get("_tool_registry") or g.get("_desktop_tool_registry")
        if reg is None:
            return "Tool registry not available — Ava may still be booting.", "confusion"
        result = reg.execute_tool("diagnostic_self", {}, g)
        if isinstance(result, dict) and result.get("ok"):
            summary = str(result.get("summary_text") or "").strip()
            if summary:
                # Cap spoken length — the full report can be ~30 lines.
                # First few lines are the headline; rest goes in chat history.
                head = summary.split("\n")
                lead = "\n".join(head[: min(len(head), 12)])
                if len(head) > 12:
                    lead += f"\n(plus {len(head) - 12} more diagnostic lines in the full report)"
                return lead, "focused"
        return "Diagnostic ran but produced no output. Check the tool registry.", "confusion"
    except Exception as e:
        return f"Diagnostic failed: {type(e).__name__}: {str(e)[:120]}", "frustration"


# ── Mute / sleep / wake ──────────────────────────────────────────────────────

@_builtin(r"^\s*(?:mute|stop talking|be quiet|hush|shush)\s*$")
def _cmd_mute(text, m, g):
    # Speak before flipping the flag so the confirmation gets through.
    g["_tts_muted"] = True
    return "Muted.", "neutral"


@_builtin(r"^\s*(?:unmute|you can talk|talk again|speak again|come back)\s*$")
def _cmd_unmute(text, m, g):
    g["_tts_muted"] = False
    return "I'm back.", "joy"


@_builtin(
    r"\b(?:restart yourself|reboot yourself|please restart|"
    r"updates? (?:are )?queued|update(?:s)? (?:and )?restart|"
    r"reboot now)\b"
)
def _cmd_restart_with_handoff(text, m, g):
    """Acknowledge + write handoff JSON + signal watchdog.

    Task 5 (2026-05-02). User-facing pattern from
    docs/CONTINUOUS_INTERIORITY.md §2: she gives a time estimate
    (with safety buffer), saves a handoff JSON, sets the watchdog
    flag, exits. On next boot, brain/restart_handoff.read_handoff_on_
    boot reconstructs the time_offline and surfaces it to inner
    monologue.

    The estimate here is a sane default (15 s actual + 25 % buffer
    that the handoff stores). Boot really takes longer in practice
    (~3 min on cold cache) but this command is for fast restarts
    after small updates; sleep-mode-style wake-up tracking lives in
    the longer-term roadmap.
    """
    try:
        from brain.restart_handoff import write_handoff, signal_restart
    except Exception as e:
        return f"Restart handoff module unavailable: {e}", "confusion"

    estimate_seconds = 15.0  # rough; boot speed varies, the buffer covers it
    spoken = (
        f"Okay — restarting myself. I'll be back in about {int(estimate_seconds)} seconds, "
        "though it might take a little longer. See you on the other side."
    )
    try:
        write_handoff(
            g,
            estimate_seconds=estimate_seconds,
            trigger="voice_command",
            spoken_acknowledgment=spoken,
        )
        signal_restart(g)
        # Schedule a clean exit on a small delay so the spoken
        # acknowledgment lands before the process dies. Don't kill
        # the worker thread that's about to TTS this reply.
        import threading as _t
        import os as _os
        def _delayed_exit():
            import time as _time
            _time.sleep(8.0)  # let TTS finish + give watchdog a beat
            print("[restart_handoff] exiting cleanly via voice_command trigger")
            _os._exit(0)
        _t.Thread(target=_delayed_exit, daemon=True, name="restart-exit").start()
        return spoken, "focused"
    except Exception as e:
        return f"Restart attempt failed: {type(e).__name__}: {str(e)[:120]}", "frustration"


@_builtin(r"\b(?:go to sleep|ava sleep|sleep now)\b")
def _cmd_sleep(text, m, g):
    vl = g.get("_voice_loop")
    if vl is not None:
        try:
            vl._set_state("passive")  # type: ignore[attr-defined]
        except Exception:
            pass
    return "Going to sleep.", "calm"


@_builtin(r"\b(?:wake up|ava wake up|are you awake)\b")
def _cmd_wake(text, m, g):
    vl = g.get("_voice_loop")
    if vl is not None:
        try:
            vl._set_state("attentive")  # type: ignore[attr-defined]
        except Exception:
            pass
    return "I'm here.", "joy"


# ── Help ─────────────────────────────────────────────────────────────────────

@_builtin(r"\b(?:what can you do|help|commands|list commands)\b")
def _cmd_help(text, m, g):
    summary = (
        "I can open apps, switch tabs, set reminders, move my widget, "
        "read my journal, tell time, and learn new commands. "
        "Try 'open chrome', 'remind me to drink water in 15 minutes', "
        "'move to top right', or 'make a command'."
    )
    return summary, "calm"


# ── App control ──────────────────────────────────────────────────────────────

@_builtin(r"\bopen (.+?)$")
def _cmd_open(text, m, g):
    target = m.group(1).strip()
    # Avoid stealing "open journal" etc — if a more-specific tab handler
    # would have matched, this regex still wins (longer specific patterns are
    # registered earlier). Filter out obvious non-app targets here.
    if target.lower() in ("the journal", "journal", "memory", "brain", "status", "tools", "models", "debug", "people"):
        # Already handled by tab handlers — shouldn't get here, but be safe.
        return "", ""
    ok, msg = _route_open_app(target, g)
    return msg, "joy" if ok else "calm"


@_builtin(r"\b(?:close|quit|kill) (.+?)$")
def _cmd_close(text, m, g):
    target = m.group(1).strip()
    try:
        from tools.system.app_launcher import _tool_close_app
        res = _tool_close_app({"app_name": target}, g)
        if res.get("ok"):
            return f"Closed {target}.", "calm"
    except Exception:
        pass
    return f"I couldn't close {target}.", "calm"


@_builtin(r"\bplay (?:the )?dino(?: game)?\b")
def _cmd_dino(text, m, g):
    try:
        from tools.system.browser_tool import _tool_open_dino_game
        _tool_open_dino_game({}, g)
        return "Opening the dino game.", "joy"
    except Exception:
        return "I couldn't open it.", "calm"


# ── Widget movement ──────────────────────────────────────────────────────────

@_builtin(r"\bmove (?:to|the widget to)? ?top right\b")
def _cmd_widget_top_right(text, m, g):
    ok, msg = _route_move_widget("top_right", g)
    return msg, "neutral"


@_builtin(r"\bmove (?:to|the widget to)? ?top left\b")
def _cmd_widget_top_left(text, m, g):
    ok, msg = _route_move_widget("top_left", g)
    return msg, "neutral"


@_builtin(r"\bmove (?:to|the widget to)? ?bottom right\b|\bget out of (?:the )?way\b")
def _cmd_widget_bottom_right(text, m, g):
    ok, msg = _route_move_widget("bottom_right", g)
    return msg, "neutral"


@_builtin(r"\bmove (?:to|the widget to)? ?bottom left\b")
def _cmd_widget_bottom_left(text, m, g):
    ok, msg = _route_move_widget("bottom_left", g)
    return msg, "neutral"


@_builtin(r"\bcome (?:here|back)\b|\bmove (?:to|the widget to)? ?(?:center|centre|middle)\b")
def _cmd_widget_center(text, m, g):
    ok, msg = _route_move_widget("center", g)
    return msg, "joy"


@_builtin(r"\bmove (?:to|the widget to)? ?left\b")
def _cmd_widget_left(text, m, g):
    ok, msg = _route_move_widget("left", g)
    return msg, "neutral"


@_builtin(r"\bmove (?:to|the widget to)? ?right\b")
def _cmd_widget_right(text, m, g):
    ok, msg = _route_move_widget("right", g)
    return msg, "neutral"


# ── Reminders ────────────────────────────────────────────────────────────────

@_builtin(r"\bremind me to (.+?) in (\d+(?:\.\d+)?) ?(minutes?|min|seconds?|sec|hours?|hrs?)\b")
def _cmd_set_reminder(text, m, g):
    what = m.group(1).strip()
    n = float(m.group(2))
    unit = m.group(3).lower()
    if unit.startswith("sec"):
        minutes = n / 60.0
    elif unit.startswith("hour") or unit.startswith("hr"):
        minutes = n * 60.0
    else:
        minutes = n
    try:
        from tools.system.reminder_tool import set_reminder
        set_reminder(what, minutes, g)
    except Exception as e:
        print(f"[voice_commands] reminder error: {e}")
        return "I couldn't set that reminder.", "neutral"
    if minutes >= 60:
        return f"I'll remind you in {minutes/60:.1f} hours.", "calm"
    if minutes < 1:
        return f"I'll remind you in {minutes*60:.0f} seconds.", "calm"
    return f"I'll remind you in {minutes:.0f} minutes.", "calm"


@_builtin(r"\bwhat reminders (?:do i have|are pending)\b|\blist (?:my )?reminders\b")
def _cmd_list_reminders(text, m, g):
    try:
        from tools.system.reminder_tool import get_reminders
        pending = get_reminders(g)
    except Exception:
        return "Couldn't read reminders.", "neutral"
    if not pending:
        return "No reminders pending.", "calm"
    summary = ", ".join(str(r.get("text", ""))[:50] for r in pending[:5])
    return f"You have {len(pending)} reminder{'s' if len(pending) != 1 else ''}: {summary}.", "neutral"


@_builtin(r"\bcancel (?:my |all )?reminders?\b")
def _cmd_cancel_reminders(text, m, g):
    try:
        from tools.system.reminder_tool import cancel_reminders
        n = cancel_reminders(g)
    except Exception:
        return "Couldn't cancel reminders.", "neutral"
    return f"Cancelled {n} reminder{'s' if n != 1 else ''}.", "calm"


# ── Command/tab builder ──────────────────────────────────────────────────────

@_builtin(r"\b(?:make|create) (?:a )?command\b")
def _cmd_make_command(text, m, g):
    try:
        from brain.command_builder import get_command_builder
        cb = get_command_builder()
        if cb is None:
            return "Command builder isn't ready.", "neutral"
        question = cb.begin_command_creation("new command", g)
        return question, "curiosity"
    except Exception:
        return "Command builder unavailable.", "neutral"


@_builtin(r"\b(?:remember that|when i say) (?:['\"]?)([^'\"]+?)(?:['\"]?) (?:means|should|do) (.+)$")
def _cmd_remember_means(text, m, g):
    phrase = m.group(1).strip()
    action = m.group(2).strip()
    try:
        from brain.command_builder import get_command_builder
        cb = get_command_builder()
        if cb is None:
            return "Couldn't save that.", "neutral"
        cb.create_command(phrase, action, description="learned via 'remember that'")
        return f"Got it — '{phrase}' means {action}.", "joy"
    except Exception:
        return "Couldn't save that.", "neutral"


@_builtin(r"\b(?:make|create) (?:a )?tab (?:called |named )?(.+?)$")
def _cmd_make_tab(text, m, g):
    name = m.group(1).strip()
    if not name:
        return "What should I call the tab?", "curiosity"
    try:
        from brain.command_builder import get_command_builder
        cb = get_command_builder()
        if cb is None:
            return "Command builder unavailable.", "neutral"
        question = cb.begin_tab_creation(name, g)
        return question, "curiosity"
    except Exception:
        return "Couldn't create that tab.", "neutral"


# ── Pointing / clarification ─────────────────────────────────────────────────

@_builtin(r"\b(?:show me|where is) (.+?)(?: on screen)?$")
def _cmd_point_at(text, m, g):
    desc = m.group(1).strip()
    if not desc or len(desc) > 80:
        return "", ""  # don't intercept long phrases here
    try:
        from tools.system.pointer_tool import _point_at_element
        res = _point_at_element({"description": desc, "duration_seconds": 5.0}, g)
        if res.get("ok"):
            return f"Pointing at {desc}.", "curiosity"
    except Exception:
        pass
    return "", ""


# ── mem0 memory commands ─────────────────────────────────────────────────────

@_builtin(r"\bwhat do you (?:remember|know) about me\b|\bwhat do you (?:remember|know) about (?:zeke|ezekiel)\b")
def _cmd_remember_me(text, m, g):
    am = g.get("_ava_memory")
    if am is None or not getattr(am, "available", False):
        return "My long-term memory isn't ready yet.", "calm"
    try:
        hits = am.search("zeke preferences personality habits values", user_id="zeke", limit=5)
    except Exception as e:
        print(f"[voice_cmd remember_me] {e}")
        return "I'm having trouble pulling that up right now.", "calm"
    if not hits:
        return "Nothing's stuck yet — we haven't talked enough for me to remember much.", "calm"
    lines = [str(h.get("memory") or "").strip() for h in hits if h.get("memory")]
    lines = [l for l in lines if l][:3]
    if not lines:
        return "Nothing solid to share yet.", "calm"
    return "I remember: " + "; ".join(lines) + ".", "curiosity"


@_builtin(r"\bdo you remember (?:when|that) (.+?)\??$")
def _cmd_remember_when(text, m, g):
    query = (m.group(1) or "").strip()
    am = g.get("_ava_memory")
    if am is None or not getattr(am, "available", False) or not query:
        return "I'd need a memory system to answer that.", "calm"
    try:
        hits = am.search(query, user_id="zeke", limit=3)
    except Exception:
        return "Can't search right now.", "calm"
    if not hits:
        return f"Nothing on '{query[:30]}' in my memory.", "calm"
    top = str(hits[0].get("memory") or "").strip()
    if not top:
        return "Found something but it's empty.", "calm"
    return f"Yes — {top}.", "curiosity"


@_builtin(r"^\s*(?:forget that|forget what i (?:just )?said)\s*$")
def _cmd_forget_that(text, m, g):
    am = g.get("_ava_memory")
    if am is None or not getattr(am, "available", False):
        return "I can't forget what I never wrote down.", "calm"
    # Find the most recent memory and delete it.
    try:
        all_mem = am.get_all(user_id="zeke", limit=200)
    except Exception:
        return "Can't reach memory right now.", "calm"
    if not all_mem:
        return "Nothing to forget.", "calm"
    # Sort by created_at desc and take the newest.
    def _ts(m):
        return str(m.get("created_at") or "")
    all_mem.sort(key=_ts, reverse=True)
    target = all_mem[0]
    mid = target.get("id")
    if mid and am.delete(mid):
        snippet = str(target.get("memory") or "")[:60]
        return f"Forgot that ({snippet}).", "neutral"
    return "Couldn't delete it.", "calm"


@_builtin(r"\bforget everything (?:you know )?about (.+?)$")
def _cmd_forget_about(text, m, g):
    topic = (m.group(1) or "").strip()
    am = g.get("_ava_memory")
    if am is None or not getattr(am, "available", False) or not topic:
        return "Can't do that right now.", "calm"
    try:
        n = am.delete_matching(topic, user_id="zeke")
    except Exception:
        return "Couldn't reach memory.", "calm"
    if n == 0:
        return f"Nothing matching '{topic[:30]}' found.", "calm"
    return f"Cleared {n} memor{'ies' if n != 1 else 'y'} about {topic[:30]}.", "neutral"


@_builtin(r"^\s*remember this[:,]?\s*(.+?)$")
def _cmd_remember_this(text, m, g):
    fact = (m.group(1) or "").strip()
    am = g.get("_ava_memory")
    if am is None or not getattr(am, "available", False) or not fact:
        return "Memory not ready.", "calm"
    try:
        am.add_fact(fact, user_id="zeke")
    except Exception as e:
        print(f"[voice_cmd remember_this] {e}")
        return "Couldn't save that.", "calm"
    return "Got it — I'll remember.", "joy"


# ── Signal-bus awareness ────────────────────────────────────────────────────

@_builtin(r"\bwhat (?:was )?the last thing (?:i|you) copied\b")
def _cmd_last_clipboard(text, m, g):
    content = str(g.get("_clipboard_content") or "").strip()
    ctype = str(g.get("_clipboard_type") or "text")
    if not content:
        return "Nothing copied recently.", "calm"
    # Trim to a speakable summary.
    snippet = content[:160]
    return f"You copied {ctype}: {snippet}", "neutral"


@_builtin(r"\bwhat am i (?:working on|doing)\b|\bwhat(?:'s|s)? on (?:my |the )?screen\b")
def _cmd_screen_context(text, m, g):
    ctx = str(g.get("_screen_context") or "").strip()
    title = str(g.get("_active_window_title") or "").strip()
    if not ctx and not title:
        return "Nothing tracked yet.", "calm"
    if title and ctx:
        # Friendly phrasing per context.
        verb_map = {
            "coding": "coding in",
            "browsing": "browsing in",
            "watching": "watching in",
            "listening": "listening in",
            "gaming": "playing in",
            "file_management": "looking at files in",
            "productivity": "working in",
            "idle": "idle on",
            "general": "in",
        }
        verb = verb_map.get(ctx, "in")
        return f"Looks like you're {verb} {title[:60]}.", "neutral"
    return f"Screen: {ctx or 'unknown'}.", "neutral"


@_builtin(r"\bwhat signals have you noticed\b|\bwhat have you (?:seen|noticed)\b")
def _cmd_signal_recap(text, m, g):
    try:
        from brain.signal_bus import get_signal_bus
        bus = get_signal_bus()
        if bus is None:
            return "I'm not tracking signals right now.", "neutral"
        stats = bus.stats()
    except Exception:
        return "Can't read the signal bus.", "neutral"
    fc = stats.get("fire_count") or {}
    if not fc:
        return "Nothing notable.", "calm"
    parts = []
    if fc.get("clipboard_changed"):
        parts.append(f"{fc['clipboard_changed']} clipboard change{'s' if fc['clipboard_changed'] != 1 else ''}")
    if fc.get("window_changed"):
        parts.append(f"{fc['window_changed']} window switch{'es' if fc['window_changed'] != 1 else ''}")
    if fc.get("face_appeared"):
        parts.append(f"face appeared {fc['face_appeared']} time{'s' if fc['face_appeared'] != 1 else ''}")
    if fc.get("expression_changed"):
        parts.append(f"{fc['expression_changed']} expression change{'s' if fc['expression_changed'] != 1 else ''}")
    if fc.get("app_installed"):
        parts.append(f"{fc['app_installed']} install signal{'s' if fc['app_installed'] != 1 else ''}")
    if not parts:
        # Fall back to whatever else is in the count dict.
        parts = [f"{v} {k}" for k, v in list(fc.items())[:5]]
    return "I noticed " + ", ".join(parts) + ".", "curiosity"


# ── Sleep mode commands ──────────────────────────────────────────────────────

@_builtin(r"\bgo to sleep\b|\bgood ?night\b|\btake a nap\b|\bsleep for\b|\bsleep until\b")
def _cmd_sleep(text, m, g):
    """Sleep voice trigger. Parses duration; if absent, asks back."""
    try:
        from brain.sleep_mode import parse_sleep_voice_command, request_sleep
    except Exception as e:
        return f"Sleep mode unavailable: {e!r}", "calmness"
    parsed = parse_sleep_voice_command(text)
    if not parsed.get("sleep_intent"):
        # The regex matched but parse said no — defensive guard
        return "I heard you but I'm not sure if you want me to sleep. Want me to go to sleep?", "calmness"
    if parsed.get("ask_back"):
        # Stash a pending sleep state so the next user reply can be parsed as duration.
        g["_sleep_awaiting_duration_since"] = time.time()
        return "How long do you want me to sleep for?", "calmness"
    duration_s = float(parsed["duration_s"])
    request_sleep(g, duration_s=duration_s, trigger="voice", trigger_summary={"command_text": text})
    minutes = duration_s / 60.0
    label = f"{int(minutes)} minutes" if minutes >= 1 else f"{int(duration_s)} seconds"
    return f"Going to sleep for {label}. See you on the other side.", "calmness"


@_builtin(r"\bwake up\b|\bare you (?:awake|there)\b|\bcome back\b")
def _cmd_wake(text, m, g):
    """External wake provocation — only acts if currently sleeping."""
    try:
        from brain.sleep_mode import get_state, request_wake, STATE_AWAKE
    except Exception as e:
        return None, None  # let other handlers route the message
    if get_state(g) == STATE_AWAKE:
        return None, None  # not sleeping; let normal pipeline handle the greeting
    request_wake(g, reason="voice_provocation")
    return "I see you. Let me wake up.", "calmness"


# ── Custom commands loaded at runtime ────────────────────────────────────────

class _CustomCommand:
    """A command loaded from state/custom_commands.json."""

    def __init__(self, trigger: str, action: str, description: str, params: dict[str, Any]):
        self.trigger = trigger.lower().strip()
        self.action = action.strip()
        self.description = description
        self.params = dict(params or {})

    def matches(self, text: str) -> bool:
        if not self.trigger:
            return False
        return self.trigger in text  # text already lowercased

    def execute(self, g: dict[str, Any]) -> tuple[str, str]:
        """Best-effort execute. Returns (response, emotion)."""
        action = self.action
        # Action format conventions:
        #   tab:<name>             → switch to tab
        #   open:<app>             → open app
        #   move:<position>        → move widget
        #   say:<text>             → speak text
        #   tool:<name>:<json>     → call a registered tool with kwargs JSON
        if action.startswith("tab:"):
            _set_requested_tab(g, action[len("tab:"):].strip())
            return "Switched.", "neutral"
        if action.startswith("open:"):
            ok, msg = _route_open_app(action[len("open:"):].strip(), g)
            return msg, "joy" if ok else "calm"
        if action.startswith("move:"):
            ok, msg = _route_move_widget(action[len("move:"):].strip(), g)
            return msg, "neutral"
        if action.startswith("say:"):
            return action[len("say:"):].strip(), "neutral"
        if action.startswith("tool:"):
            try:
                _, name, payload = action.split(":", 2)
                params = json.loads(payload) if payload.strip().startswith("{") else {}
                from tools.tool_registry import get_tool
                tool = get_tool(name.strip())
                if tool is not None:
                    tool.handler(params, g)
            except Exception as e:
                print(f"[voice_commands] custom tool error: {e}")
            return "Done.", "neutral"
        # Fallback: assume the action is plain text Ava should say.
        return action, "neutral"


# ── Router ────────────────────────────────────────────────────────────────────

class VoiceCommandRouter:
    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._lock = threading.Lock()
        self._custom: list[_CustomCommand] = []
        self.reload_custom_commands()

    def reload_custom_commands(self) -> None:
        try:
            from brain.command_builder import get_command_builder
            cb = get_command_builder(self._base)
            commands = cb.load_commands() if cb else []
        except Exception:
            commands = []
        with self._lock:
            self._custom = [
                _CustomCommand(
                    trigger=str(c.get("trigger") or ""),
                    action=str(c.get("action") or ""),
                    description=str(c.get("description") or ""),
                    params=c.get("params") or {},
                )
                for c in commands
                if isinstance(c, dict) and c.get("trigger") and c.get("action")
            ]
        if self._custom:
            print(f"[voice_commands] loaded {len(self._custom)} custom commands")

    def route(
        self,
        text: str,
        g: dict[str, Any],
        *,
        allow_correction: bool = True,
    ) -> tuple[bool, str]:
        """Dispatch. Returns (handled, response_text).

        IMPORTANT: route() does NOT enqueue TTS for the response. TTS is
        the responsibility of voice_loop._speak(), which fires once after
        run_ava returns. Tonight's hardware test caught a double-playback
        bug where both this router AND voice_loop enqueued the same reply
        — the same audio played twice through speakers. Single dispatcher
        eliminates the duplication.

        If you need to speak from a non-run_ava code path (e.g. a tool
        result), call worker.speak_with_emotion() directly. Do NOT call
        _say() from inside route().
        """
        if not text or not text.strip():
            return False, ""
        # Stash for correction handler.
        g["_last_user_input_pre_router"] = text

        normalised = _norm(text)

        # Resume in-progress interactive flows (command/tab creation).
        try:
            from brain.command_builder import get_command_builder
            cb = get_command_builder()
            if cb is not None and isinstance(g.get("_command_builder_pending"), dict):
                resumed = cb.resume_pending(text, g)
                if resumed is not None:
                    response = str(resumed.get("response") or "")
                    return True, response
        except Exception:
            pass

        # Correction phrases first.
        if allow_correction:
            try:
                from brain.correction_handler import get_correction_handler
                ch = get_correction_handler()
                if ch is not None:
                    handled = ch.handle(text, g)
                    if handled is not None:
                        response = str(handled.get("response") or "")
                        # Track action attempt.
                        g["_last_action"] = {"trigger": text, "kind": "correction"}
                        return True, response
            except Exception:
                pass

        # Builtin commands.
        for pattern, handler in _BUILTINS:
            m = pattern.search(normalised)
            if m is None:
                continue
            try:
                response, emotion = handler(normalised, m, g)
            except Exception as e:
                print(f"[voice_commands] handler error for {pattern.pattern!r}: {e}")
                continue
            if not response:
                # Handler explicitly declined to act (e.g. open journal → tab handler).
                continue
            # Stash emotion for voice_loop to pick up on the speak.
            g["_voice_command_emotion"] = emotion or "neutral"
            g["_last_action"] = {"trigger": text, "kind": "builtin", "pattern": pattern.pattern}
            return True, response

        # Custom commands.
        with self._lock:
            customs = list(self._custom)
        for cc in customs:
            if cc.matches(normalised):
                try:
                    response, emotion = cc.execute(g)
                except Exception as e:
                    print(f"[voice_commands] custom error: {e}")
                    continue
                if response:
                    g["_voice_command_emotion"] = emotion or "neutral"
                g["_last_action"] = {"trigger": text, "kind": "custom", "trigger_phrase": cc.trigger}
                return True, response

        return False, ""


# ── singleton ─────────────────────────────────────────────────────────────────

_SINGLETON: Optional[VoiceCommandRouter] = None
_LOCK = threading.Lock()


def get_voice_command_router(base_dir: Optional[Path] = None) -> Optional[VoiceCommandRouter]:
    global _SINGLETON
    if _SINGLETON is not None:
        return _SINGLETON
    if base_dir is None:
        return None
    with _LOCK:
        if _SINGLETON is None:
            _SINGLETON = VoiceCommandRouter(Path(base_dir))
    return _SINGLETON


def bootstrap_voice_command_router(g: dict[str, Any]) -> Optional[VoiceCommandRouter]:
    base = Path(g.get("BASE_DIR") or ".")
    r = get_voice_command_router(base)
    g["_voice_command_router"] = r
    return r


# ── builtin count for reports ─────────────────────────────────────────────────

def builtin_count() -> int:
    return len(_BUILTINS)
