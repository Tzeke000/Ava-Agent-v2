from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"\b([A-Z][a-z]{1,20})\b")


@dataclass
class IdentityMatch:
    canonical_name: str
    matched_as: str
    confidence: float


class IdentityRegistry:
    def __init__(self, profiles_dir: Path, settings: dict[str, Any]) -> None:
        self.profiles_dir = profiles_dir
        self.settings = settings
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_profile('zeke', aliases=['ezekiel', 'creator', 'your creator'])
        self._ensure_profile('shonda', aliases=['mom', 'mother', 'my mom'])

    def _profile_path(self, slug: str) -> Path:
        return self.profiles_dir / f'{slug}.json'

    def _ensure_profile(self, slug: str, aliases: list[str] | None = None) -> None:
        path = self._profile_path(slug)
        if not path.exists():
            path.write_text(json.dumps({'name': slug, 'aliases': aliases or []}, indent=2), encoding='utf-8')

    def export_profiles(self) -> dict[str, Any]:
        result = {}
        for p in sorted(self.profiles_dir.glob('*.json')):
            try:
                result[p.stem] = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                result[p.stem] = {'error': 'unreadable'}
        return result

    def resolve_from_text(self, text: str) -> IdentityMatch | None:
        low = text.lower()
        profiles = self.export_profiles()
        for slug, info in profiles.items():
            aliases = [slug.lower()] + [a.lower() for a in info.get('aliases', [])]
            for alias in aliases:
                if alias and alias in low:
                    return IdentityMatch(canonical_name=slug, matched_as=alias, confidence=0.95)
        m = NAME_RE.search(text)
        if m:
            return IdentityMatch(canonical_name=m.group(1).lower(), matched_as=m.group(1), confidence=0.45)
        return None
