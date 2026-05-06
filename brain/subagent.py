"""brain/subagent.py — Background delegation for long-running queries.

Hermes-pattern subagent. When the user asks an open-ended factual /
knowledge question that would otherwise hang the deep-path for 60-120s
(e.g., "tell me about polar bears"), Ava acknowledges quickly ("let me
look into that") and runs the actual query in a background thread.
When it completes, she announces the answer via TTS and writes to
chat_history.

Trade-off: user gets immediate responsiveness for the cost of a
two-stage reply. For genuinely slow knowledge queries, this is much
better than 120s of dead air followed by a "Hold on..." fallback.

Detection heuristic (in `looks_like_knowledge_query`):
- Has knowledge-question shape ("tell me about", "what is", "explain",
  "describe", "how does", "give me information on") OR
- Has a `?` and ≥7 words (long enough to need deep reasoning)
- AND no command-shaped verb (open/close/launch/etc) — those are
  action queries, not knowledge.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

_KNOWLEDGE_PATTERNS = re.compile(
    r"\b(?:"
    r"tell me about"
    r"|tell me more about"
    r"|what is"
    r"|what are"
    r"|explain"
    r"|describe"
    r"|how does"
    r"|how do"
    r"|why does"
    r"|why do"
    r"|give me information"
    r"|give me a summary"
    r")\b",
    re.IGNORECASE,
)
_COMMAND_VERBS = re.compile(
    r"\b(?:open|close|quit|kill|launch|start|run|play|stop|end|"
    r"type|paste|copy|search the web|search for|find|"
    r"weather|raining|snowing|sunny|temperature|"
    r"time|date|today|tomorrow|"
    r"remind|reminder|note|save|build|fix|"
    r"who am i|how are you|what do you (?:want|need)|tell me about yourself)\b",
    re.IGNORECASE,
)


def looks_like_knowledge_query(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if _COMMAND_VERBS.search(t):
        return False
    if _KNOWLEDGE_PATTERNS.search(t):
        return True
    if "?" in t and len(t.split()) >= 7:
        return True
    return False


def _persist_assistant(g: dict[str, Any], content: str, *, model: str) -> None:
    """Append the deferred reply to chat_history.jsonl + canonical history."""
    try:
        from pathlib import Path as _P
        base = _P(g.get("BASE_DIR") or ".")
        hp = base / "state" / "chat_history.jsonl"
        hp.parent.mkdir(parents=True, exist_ok=True)
        person = (
            g.get("_active_person_id")
            or g.get("active_person_id")
            or "zeke"
        )
        with hp.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "role": "assistant",
                "source": "ava_response",
                "content": content,
                "person_id": person,
                "model": model,
                "emotion": "neutral",
                "turn_route": "subagent",
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[subagent] chat_history append error: {e!r}")
    try:
        import avaagent as _av
        _canon = list(_av._get_canonical_history())
        _canon.append({"role": "assistant", "content": content})
        _av._set_canonical_history(_canon)
    except Exception:
        pass


def _run_in_background(text: str, g: dict[str, Any]) -> None:
    """Execute the deep-path LLM call and announce the result via TTS."""
    print(f"[subagent] background query starting: {text[:80]!r}")
    t0 = time.time()
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import SystemMessage, HumanMessage
        from brain.ollama_lock import with_ollama
    except Exception as e:
        print(f"[subagent] import error: {e!r}")
        return

    sys_prompt = (
        "You are Ava, a local AI companion. Answer the user's question in "
        "1-3 short, natural sentences. Be specific and helpful. If you "
        "genuinely don't know, say so briefly — don't make things up."
    )
    try:
        llm = ChatOllama(
            model="ava-personal:latest",
            temperature=0.55,
            num_predict=180,
            keep_alive=-1,
        )
        result = with_ollama(
            lambda: llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=text.strip()),
            ]),
            label="subagent:ava-personal",
        )
        reply = (getattr(result, "content", "") or "").strip()
        elapsed = time.time() - t0
        print(f"[subagent] answer in {elapsed:.1f}s: {reply[:120]!r}")
    except Exception as e:
        print(f"[subagent] LLM error: {e!r}")
        return

    if not reply:
        return

    # B4: wrap reply with confidence-appropriate caveat. Subagent
    # answers from LLM training data unless we explicitly looked it
    # up. Default to "training" source which yields medium confidence
    # + "that's from my training data" tail note.
    try:
        from brain.confidence import wrap_for_source
        reply_with_caveat = wrap_for_source(reply, source_kind="training")
    except Exception:
        reply_with_caveat = reply

    # Speak via TTS worker.
    worker = g.get("_tts_worker")
    if worker is not None and getattr(worker, "available", False):
        try:
            worker.speak(reply_with_caveat, emotion="curiosity", intensity=0.5, blocking=False)
        except Exception as e:
            print(f"[subagent] TTS speak error: {e!r}")

    _persist_assistant(g, reply_with_caveat, model="ava-personal:latest")


def delegate(text: str, g: dict[str, Any]) -> str:
    """Spawn a background thread for the query. Returns the immediate
    acknowledgement Ava should speak right now.
    """
    threading.Thread(
        target=_run_in_background,
        args=(text, g),
        daemon=True,
        name="ava-subagent",
    ).start()
    # Vary the acknowledgement so it doesn't feel templated.
    import random
    acks = [
        "Let me look into that — give me a moment.",
        "Hmm, good question. Thinking on it — back in a sec.",
        "Let me think about that for a moment.",
        "Hold on — I'll dig into that and tell you what I find.",
    ]
    return random.choice(acks)
