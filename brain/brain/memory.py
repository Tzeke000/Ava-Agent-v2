from __future__ import annotations
from .shared import extract_text

def search_reflections(host, query, *args, **kwargs):
    # Preserve old memory files and retrieval behavior by delegating to the
    # existing reflection search implementation. This module is a safe bridge.
    orig = host.get('_BRAIN_ORIG_SEARCH_REFLECTIONS')
    if callable(orig):
        return orig(query, *args, **kwargs)
    return []

def describe_memory_integrity(host):
    fn = host.get('get_memory_status')
    if callable(fn):
        try: return str(fn())
        except Exception as e: return f'error: {e}'
    return 'memory status unavailable'
