from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


@dataclass
class CuriosityTopic:
    topic: str
    sparked_by: str
    ts_added: float
    times_thought_about: int
    resolved: bool
    priority: float


def _state_path(base_dir: Path) -> Path:
    return base_dir / "state" / "curiosity_topics.json"


def _load(base_dir: Path) -> dict[str, Any]:
    p = _state_path(base_dir)
    if not p.is_file():
        return {"topics": []}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("topics", [])
            return d
    except Exception:
        pass
    return {"topics": []}


def _save(base_dir: Path, st: dict[str, Any]) -> None:
    p = _state_path(base_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _topic_similarity(a: str, b: str) -> float:
    sa = set((a or "").lower().split())
    sb = set((b or "").lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def add_topic(topic: str, sparked_by: str, g: dict[str, Any]) -> None:
    t = " ".join((topic or "").split()).strip()[:180]
    if not t:
        return
    base_dir = Path(g.get("BASE_DIR") or Path.cwd())
    st = _load(base_dir)
    rows = list(st.get("topics") or [])
    now = time.time()
    for row in rows:
        prev = str(row.get("topic") or "")
        if _topic_similarity(t, prev) >= 0.7:
            row["times_thought_about"] = int(row.get("times_thought_about", 1) or 1) + 1
            row["priority"] = min(1.0, float(row.get("priority", 0.4) or 0.4) + 0.08)
            row["resolved"] = False
            _save(base_dir, {"topics": rows[:20]})
            g["_current_curiosity_topic"] = prev
            return
    rows.append(
        asdict(
            CuriosityTopic(
                topic=t,
                sparked_by=str(sparked_by or "")[:220],
                ts_added=now,
                times_thought_about=1,
                resolved=False,
                priority=0.55,
            )
        )
    )
    rows = sorted(rows, key=lambda x: float(x.get("priority", 0.0) or 0.0), reverse=True)[:20]
    _save(base_dir, {"topics": rows})
    g["_current_curiosity_topic"] = t


def get_current_curiosity(g: dict[str, Any] | None = None) -> dict[str, Any] | None:
    base_dir = Path((g or {}).get("BASE_DIR") or Path.cwd())
    st = _load(base_dir)
    rows = list(st.get("topics") or [])
    now = time.time()
    best = None
    best_score = -1.0
    for row in rows:
        if bool(row.get("resolved", False)):
            continue
        recency = max(0.0, 1.0 - (now - float(row.get("ts_added") or now)) / (7 * 24 * 3600))
        thought_weight = min(1.0, float(row.get("times_thought_about", 1) or 1) / 6.0)
        score = 0.58 * recency + 0.42 * thought_weight + 0.25 * float(row.get("priority", 0.0) or 0.0)
        if score > best_score:
            best = row
            best_score = score
    return best


def mark_resolved(topic: str, g: dict[str, Any] | None = None) -> None:
    base_dir = Path((g or {}).get("BASE_DIR") or Path.cwd())
    st = _load(base_dir)
    rows = list(st.get("topics") or [])
    for row in rows:
        if _topic_similarity(str(row.get("topic") or ""), topic) >= 0.7:
            row["resolved"] = True
    _save(base_dir, {"topics": rows})


def bootstrap_from_chatlog(g: dict[str, Any]) -> None:
    base_dir = Path(g.get("BASE_DIR") or Path.cwd())
    st = _load(base_dir)
    if list(st.get("topics") or []):
        return
    p = base_dir / "chatlog.jsonl"
    if not p.is_file():
        return
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
    corpus = []
    for line in lines:
        try:
            row = json.loads(line)
            corpus.append(f"{row.get('role')}: {str(row.get('content') or '')[:220]}")
        except Exception:
            continue
    if not corpus:
        return
    model = "mistral:7b"
    try:
        llm = ChatOllama(model=model, temperature=0.4)
        out = llm.invoke(
            [
                SystemMessage(content="Extract 3-5 concise curiosity topics Ava might wonder about. Return JSON array of strings."),
                HumanMessage(content="\n".join(corpus)[-3000:]),
            ]
        )
        txt = (getattr(out, "content", None) or str(out)).strip()
        arr = json.loads(txt[txt.find("[") : txt.rfind("]") + 1])
        if isinstance(arr, list):
            for t in arr[:5]:
                if isinstance(t, str):
                    add_topic(t, "startup_chatlog_scan", g)
    except Exception:
        for t in ["What helps Zeke most during focused work?", "How should I pace proactive check-ins?"]:
            add_topic(t, "startup_fallback", g)
