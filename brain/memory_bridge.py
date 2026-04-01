from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryBridge:
    def __init__(self, memory_dir: Path, settings: dict[str, Any]) -> None:
        self.memory_dir = memory_dir
        self.settings = settings
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def reload_settings(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    def _old_memory_path(self) -> Path | None:
        value = (self.settings.get('old_memory_path') or '').strip()
        return Path(value) if value else None

    def read_recent_context(self, person_name: str | None = None) -> list[str]:
        out: list[str] = []
        old_path = self._old_memory_path()
        if not old_path or not old_path.exists():
            return out
        for candidate in [old_path / 'self reflection', old_path]:
            if candidate.exists():
                files = sorted(candidate.rglob('*.json'))[-5:] + sorted(candidate.rglob('*.txt'))[-5:]
                for p in files[-6:]:
                    try:
                        txt = p.read_text(encoding='utf-8', errors='ignore')
                        if person_name is None or person_name.lower() in txt.lower():
                            out.append(f'{p.name}: {txt[:300]}')
                    except Exception:
                        continue
                if out:
                    break
        return out[:6]
