"""
Process-wide Ollama serialization lock.

Ollama on this machine swaps models in/out of GPU memory. If Stream A
(reply_engine, ava-personal:latest) and Stream B (dual_brain background,
qwen2.5:14b / kimi-k2.6:cloud) try to invoke at the same time, Ollama
must unload one and load the other — adding 30s to several minutes of
latency to each turn while the swap happens.

A single global lock around every Ollama invocation forces them to
queue. Foreground turns acquire first because they call invoke() before
Stream B's worker loop wakes up; Stream B already pauses while Zeke is
active (`should_pause_background`), so contention is rare in practice
once this lock is honored.

Usage:
    from brain.ollama_lock import with_ollama
    result = with_ollama(lambda: llm.invoke(messages))

Or as a context manager:
    from brain.ollama_lock import ollama_call
    with ollama_call():
        result = llm.invoke(messages)
"""
from __future__ import annotations

import contextlib
import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")

# Use an RLock so the same thread can re-enter (e.g. when a tool call inside
# an inference triggers another inference on the same thread).
_OLLAMA_LOCK = threading.RLock()
_LAST_HOLDER: dict = {"thread": "", "label": "", "since": 0.0}


def with_ollama(fn: Callable[[], T], label: str = "") -> T:
    """Run fn() while holding the global Ollama lock. Logs wait time if >2s."""
    t0 = time.time()
    _OLLAMA_LOCK.acquire()
    waited = time.time() - t0
    if waited > 2.0:
        print(f"[ollama_lock] {label or 'invoke'} waited {waited:.1f}s for prior holder={_LAST_HOLDER.get('label')}")
    _LAST_HOLDER["thread"] = threading.current_thread().name
    _LAST_HOLDER["label"] = label
    _LAST_HOLDER["since"] = time.time()
    try:
        return fn()
    finally:
        _OLLAMA_LOCK.release()


@contextlib.contextmanager
def ollama_call(label: str = ""):
    """Context-manager form. Same semantics as with_ollama."""
    t0 = time.time()
    _OLLAMA_LOCK.acquire()
    waited = time.time() - t0
    if waited > 2.0:
        print(f"[ollama_lock] {label or 'invoke'} waited {waited:.1f}s for prior holder={_LAST_HOLDER.get('label')}")
    _LAST_HOLDER["thread"] = threading.current_thread().name
    _LAST_HOLDER["label"] = label
    _LAST_HOLDER["since"] = time.time()
    try:
        yield
    finally:
        _OLLAMA_LOCK.release()


def lock_status() -> dict:
    """For diagnostics — returns who currently holds (or last held) the lock."""
    return dict(_LAST_HOLDER)
