from typing import Dict, Any, List, Tuple


def resolve_profile_person_key(active_profile: dict | None) -> Tuple[str | None, str | None]:
    if not isinstance(active_profile, dict):
        return None, None
    for key in ("person_id", "id", "profile_id", "slug", "name"):
        value = active_profile.get(key)
        if value:
            return str(value), key
    return None, None


def build_memory_reader_summary(g: dict, user_input: str, active_profile: dict) -> str:
    person_key, used_key = resolve_profile_person_key(active_profile)
    memories: List[dict] = []
    reflections: List[dict] = []
    self_model: dict = {}
    debug_lines: List[str] = []

    if used_key:
        debug_lines.append(f"[memory-reader] using profile key: {used_key}={person_key}")
    else:
        debug_lines.append("[memory-reader] no usable profile key found")

    try:
        if 'search_memories' in g and person_key:
            memories = g['search_memories'](user_input, person_key, 5) or []
            debug_lines.append(f"[memory-reader] memories retrieved: {len(memories)}")
    except Exception as e:
        memories = []
        debug_lines.append(f"[memory-reader] search_memories failed: {e}")
    try:
        if 'load_recent_reflections' in g and person_key:
            reflections = g['load_recent_reflections'](limit=5, person_id=person_key) or []
            debug_lines.append(f"[memory-reader] reflections retrieved: {len(reflections)}")
    except Exception as e:
        reflections = []
        debug_lines.append(f"[memory-reader] load_recent_reflections failed: {e}")
    try:
        if 'load_self_model' in g:
            self_model = g['load_self_model']() or {}
    except Exception:
        self_model = {}

    try:
        for line in debug_lines:
            print(line)
    except Exception:
        pass

    mem_lines = []
    for row in memories[:3]:
        text = str(row.get('text', ''))[:180]
        if text:
            mem_lines.append(f"- {text}")
    ref_lines = []
    for row in reflections[:2]:
        text = str(row.get('reflection_text', row.get('text', '')))[:180]
        if text:
            ref_lines.append(f"- {text}")

    drives = self_model.get('core_drives', [])[:4] if isinstance(self_model, dict) else []
    patterns = self_model.get('behavior_patterns', [])[-4:] if isinstance(self_model, dict) else []
    return (
        "DYNAMIC SELF / MEMORY READER:\n"
        f"Recent relevant memories:\n{chr(10).join(mem_lines) if mem_lines else '- none retrieved'}\n"
        f"Recent reflections:\n{chr(10).join(ref_lines) if ref_lines else '- none retrieved'}\n"
        f"Current core drives: {drives if drives else 'unknown'}\n"
        f"Recent behavior patterns: {patterns if patterns else 'unknown'}\n"
        "Use this dynamic section above the static self model if they conflict."
    )
