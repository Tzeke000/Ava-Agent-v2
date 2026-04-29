"""
Phase 79 — Person onboarding system.

Conversational 13-stage flow for registering a new person with Ava.
Photos saved to faces/{person_id}/. Profile saved to profiles/{person_id}.json.

Ava decides her own greeting warmth and formality. The stages are structural
scaffolding; the words are hers to develop through experience.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

STAGES = [
    "greeting",
    "photo_front",
    "photo_left",
    "photo_right",
    "photo_up",
    "photo_down",
    "confirm_photos",
    "name_capture",
    "pronouns",
    "favorite_color",
    "relationship",
    "one_thing",
    "complete",
]

PHOTO_STAGES = {"photo_front", "photo_left", "photo_right", "photo_up", "photo_down"}

PHOTO_INSTRUCTIONS = {
    "photo_front": "Look directly at the camera with good lighting. Tell me when you're ready.",
    "photo_left":  "Slowly turn your head to the left. Tell me when you're ready.",
    "photo_right": "Now turn your head to the right. Tell me when you're ready.",
    "photo_up":    "Look slightly upward. Tell me when you're ready.",
    "photo_down":  "Look slightly downward. Tell me when you're ready.",
}

PHOTO_STAGE_ORDER = ["photo_front", "photo_left", "photo_right", "photo_up", "photo_down"]


def _base_dir(g: dict[str, Any]) -> Path:
    return Path(g.get("BASE_DIR") or ".")


def _capture_frames(n: int = 3) -> list[Any]:
    """Capture n frames from live camera. Returns list of BGR numpy arrays."""
    frames: list[Any] = []
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap.release()
            return frames
        for _ in range(n + 2):  # warm up
            cap.read()
        for _ in range(n):
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
            time.sleep(0.08)
        cap.release()
    except Exception as e:
        print(f"[onboarding] capture error: {e}")
    return frames


def _frame_quality(frame: Any) -> float:
    """0–1 quality score for a captured frame."""
    try:
        from brain.frame_quality import compute_frame_quality
        r = compute_frame_quality(frame)
        return float(r.overall_quality_score)
    except Exception:
        return 0.5


def _save_photos(person_id: str, stage: str, frames: list[Any], base_dir: Path) -> list[Path]:
    """Save frames as JPEG into faces/{person_id}/. Returns saved paths."""
    face_dir = base_dir / "faces" / person_id
    face_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    try:
        import cv2
        for i, frame in enumerate(frames):
            fname = face_dir / f"{stage}_{i}.jpg"
            cv2.imwrite(str(fname), frame)
            saved.append(fname)
    except Exception as e:
        print(f"[onboarding] save_photos error: {e}")
    return saved


def _load_profile(person_id: str, base_dir: Path) -> dict[str, Any]:
    path = base_dir / "profiles" / f"{person_id}.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_profile(person_id: str, profile: dict[str, Any], base_dir: Path) -> None:
    path = base_dir / "profiles" / f"{person_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _is_ready(text: str) -> bool:
    low = text.lower().strip()
    return any(k in low for k in ("ready", "ok", "okay", "go", "yes", "sure", "done", "yep", "yeah"))


def _is_skip(text: str) -> bool:
    low = text.lower().strip()
    return any(k in low for k in ("skip", "pass", "no", "nope", "prefer not", "rather not", "next"))


class OnboardingFlow:
    """
    Drives one person through the 13-stage onboarding sequence.

    run_step(user_input, g) → (response_text, stage_name, done)
    """

    def __init__(self, person_id: str, base_dir: Path, initial_name: Optional[str] = None):
        self.person_id = person_id
        self.base_dir = base_dir
        self.stage_index = 0
        self.photos: dict[str, list[Path]] = {}  # stage → paths
        self.photo_qualities: dict[str, float] = {}  # stage → avg quality
        self.data: dict[str, Any] = {
            "name": initial_name or "",
            "pronouns": "",
            "favorite_color": "",
            "relationship": "",
            "one_thing": "",
        }
        self._awaiting_ready = False  # True when Ava gave photo instruction, waiting for "ready"
        self._retake_stage: Optional[str] = None  # set when retake needed
        self._profile_complete = False

    @property
    def stage(self) -> str:
        return STAGES[min(self.stage_index, len(STAGES) - 1)]

    def _advance(self) -> None:
        self.stage_index = min(self.stage_index + 1, len(STAGES) - 1)
        self._awaiting_ready = False

    def run_step(self, user_input: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        """Process one turn. Returns (response, current_stage, is_done)."""
        inp = (user_input or "").strip()
        stage = self.stage

        if stage == "greeting":
            return self._handle_greeting(inp, g)
        elif stage in PHOTO_STAGES:
            return self._handle_photo_stage(inp, stage, g)
        elif stage == "confirm_photos":
            return self._handle_confirm_photos(inp, g)
        elif stage == "name_capture":
            return self._handle_name_capture(inp, g)
        elif stage == "pronouns":
            return self._handle_pronouns(inp, g)
        elif stage == "favorite_color":
            return self._handle_favorite_color(inp, g)
        elif stage == "relationship":
            return self._handle_relationship(inp, g)
        elif stage == "one_thing":
            return self._handle_one_thing(inp, g)
        elif stage == "complete":
            return self._handle_complete(g)
        return ("I'm not sure where we are. Let me start over.", "greeting", False)

    # ── stage handlers ────────────────────────────────────────────────────────

    def _handle_greeting(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        self._advance()
        instr = PHOTO_INSTRUCTIONS["photo_front"]
        self._awaiting_ready = True
        name_hint = f" I see you haven't been introduced to me yet." if not self.data["name"] else f" Nice to meet you, {self.data['name']}."
        reply = (
            f"Hi there!{name_hint} I'd love to get to know you properly — "
            f"I'll take a few photos so I can recognize you in the future, "
            f"then ask you a handful of quick questions.\n\n"
            f"First: {instr}"
        )
        return reply, self.stage, False

    def _handle_photo_stage(self, inp: str, stage: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        if self._awaiting_ready:
            if not _is_ready(inp):
                return (f"Take your time. {PHOTO_INSTRUCTIONS[stage]}", stage, False)
            # User said ready — capture photos
            self._awaiting_ready = False
            frames = _capture_frames(3)
            if not frames:
                return (
                    "I couldn't get a clear shot — my camera might not be available. "
                    "Let's skip photos for now and continue with the questions.",
                    stage,
                    False,
                )
            saved = _save_photos(self.person_id, stage, frames, self.base_dir)
            avg_q = sum(_frame_quality(f) for f in frames) / max(1, len(frames))
            self.photos[stage] = saved
            self.photo_qualities[stage] = avg_q
            print(f"[onboarding] {stage} photos={len(saved)} avg_quality={avg_q:.2f}")

            # Move to next photo stage or confirm
            idx = PHOTO_STAGE_ORDER.index(stage)
            if idx < len(PHOTO_STAGE_ORDER) - 1:
                next_stage = PHOTO_STAGE_ORDER[idx + 1]
                # Skip to that stage
                self.stage_index = STAGES.index(next_stage)
                self._awaiting_ready = True
                return (f"Got it! {PHOTO_INSTRUCTIONS[next_stage]}", self.stage, False)
            else:
                # All photo stages done
                self._advance()  # → confirm_photos
                return self._handle_confirm_photos("", g)
        else:
            # Shouldn't happen — just re-issue the instruction
            self._awaiting_ready = True
            return (PHOTO_INSTRUCTIONS[stage], stage, False)

    def _handle_confirm_photos(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        poor = [s for s, q in self.photo_qualities.items() if q < 0.35]
        if poor and inp == "":
            # First entry to confirm_photos — report quality
            issues = ", ".join(poor)
            return (
                f"I noticed the photos from {issues} might be a bit dark or blurry. "
                f"Want me to retake those, or are you happy to continue?",
                self.stage,
                False,
            )
        if inp and ("retake" in inp.lower() or "redo" in inp.lower() or "again" in inp.lower()):
            if poor:
                self._retake_stage = poor[0]
                self.stage_index = STAGES.index(poor[0])
                self._awaiting_ready = True
                return (
                    f"Sure, let's retake {poor[0].replace('_', ' ')}. "
                    f"{PHOTO_INSTRUCTIONS[poor[0]]}",
                    self.stage,
                    False,
                )
        # Photos accepted
        self._advance()  # → name_capture
        if self.data["name"]:
            # Name already known — skip name_capture
            self._advance()  # → pronouns
            return (
                f"Your photos look good, {self.data['name']}! "
                "What pronouns do you use? (Feel free to skip this.)",
                self.stage,
                False,
            )
        return (
            "Your photos look good! What's your full name, and what should I call you?",
            self.stage,
            False,
        )

    def _handle_name_capture(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        if not inp:
            return ("What's your name?", self.stage, False)
        # Try to parse "full name" / "call me X" patterns
        call_match = re.search(r"call me\s+(\w+)", inp, re.IGNORECASE)
        if call_match:
            self.data["name"] = call_match.group(1).strip()
        else:
            # Use first capitalized word or first two words
            words = inp.strip().split()
            self.data["name"] = " ".join(w for w in words[:2] if w[0].isupper()) or words[0]
        self._advance()  # → pronouns
        return (
            f"Great, {self.data['name']}! What pronouns do you use? (You can skip this if you'd prefer.)",
            self.stage,
            False,
        )

    def _handle_pronouns(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        if not inp or _is_skip(inp):
            self.data["pronouns"] = ""
        else:
            self.data["pronouns"] = inp.strip()[:50]
        self._advance()  # → favorite_color
        return (
            "What's your favorite color? I like to have a sense of you.",
            self.stage,
            False,
        )

    def _handle_favorite_color(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        self.data["favorite_color"] = inp.strip()[:50]
        self._advance()  # → relationship
        return (
            "And what's your relationship to Zeke? (For example: friend, family, colleague, partner, or something else.)",
            self.stage,
            False,
        )

    def _handle_relationship(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        self.data["relationship"] = inp.strip()[:80]
        self._advance()  # → one_thing
        return (
            "Last question: what's one thing you'd like me to remember about you?",
            self.stage,
            False,
        )

    def _handle_one_thing(self, inp: str, g: dict[str, Any]) -> tuple[str, str, bool]:
        self.data["one_thing"] = inp.strip()[:200]
        self._advance()  # → complete
        return self._handle_complete(g)

    def _handle_complete(self, g: dict[str, Any]) -> tuple[str, str, bool]:
        if not self._profile_complete:
            self._profile_complete = True
            self._save_final_profile(g)
        name = self.data.get("name") or self.person_id
        reply = (
            f"It's wonderful to meet you, {name}! I've saved your profile and photos — "
            f"I'll recognize you from now on. I hope we get to talk again soon."
        )
        return reply, "complete", True

    # ── internal ──────────────────────────────────────────────────────────────

    def _save_final_profile(self, g: dict[str, Any]) -> None:
        existing = _load_profile(self.person_id, self.base_dir)
        now_iso = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        avg_quality = (
            sum(self.photo_qualities.values()) / len(self.photo_qualities)
            if self.photo_qualities
            else 0.0
        )
        profile = {
            "person_id": self.person_id,
            "name": self.data.get("name") or self.person_id,
            "pronouns": self.data.get("pronouns") or "",
            "favorite_color": self.data.get("favorite_color") or "",
            "relationship_to_zeke": self.data.get("relationship") or "other",
            "allowed_to_use_computer": False,
            "notes": [self.data.get("one_thing")] if self.data.get("one_thing") else [],
            "likes": [],
            "dislikes": [],
            "ava_impressions": [],
            "last_seen": now_iso,
            "created_at": existing.get("created_at") or now_iso,
            "updated_at": now_iso,
            "emotion_history": existing.get("emotion_history") or ["neutral"] * 5,
            "dominant_emotion": "neutral",
            "relationship_score": existing.get("relationship_score") or 0.1,
            "interaction_count": existing.get("interaction_count") or 0,
            "onboarding_complete": True,
            "last_photo_date": now_iso,
            "quality_score": round(avg_quality, 3),
        }
        _save_profile(self.person_id, profile, self.base_dir)
        print(f"[onboarding] profile saved person_id={self.person_id} name={profile['name']}")


# ── public API ────────────────────────────────────────────────────────────────

_TRIGGER_PATTERNS = [
    re.compile(r"hey ava[,.]?\s+(?:meet|this is)\s+(.+)", re.IGNORECASE),
    re.compile(r"ava[,.]?\s+this is\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:hey ava[,.]?\s+)?(?:ava[,.]?\s+)?profile me", re.IGNORECASE),
    re.compile(r"ava[,.]?\s+profile me", re.IGNORECASE),
]

_REFRESH_PATTERNS = [
    re.compile(r"(?:hey ava[,.]?\s+)?(?:ava[,.]?\s+)?update my profile", re.IGNORECASE),
    re.compile(r"ava[,.]?\s+update my profile", re.IGNORECASE),
    re.compile(r"(?:hey ava[,.]?\s+)?(?:ava[,.]?\s+)?refresh my profile", re.IGNORECASE),
]


def detect_onboarding_trigger(user_input: str) -> tuple[bool, Optional[str]]:
    """
    Returns (triggered, name_hint).
    name_hint is extracted name if present, else None.
    """
    for pat in _TRIGGER_PATTERNS:
        m = pat.search(user_input)
        if m:
            name_hint = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else None
            return True, name_hint
    return False, None


def detect_refresh_trigger(user_input: str) -> bool:
    """Returns True if user wants to refresh/update their profile."""
    return any(p.search(user_input) for p in _REFRESH_PATTERNS)


def start_onboarding(person_id: str, base_dir: Path, name_hint: Optional[str] = None) -> OnboardingFlow:
    return OnboardingFlow(person_id, base_dir, initial_name=name_hint)


def run_onboarding_step(user_input: str, g: dict[str, Any]) -> Optional[tuple[str, str, bool]]:
    """
    If an onboarding flow is active, process one step and return (reply, stage, done).
    Returns None if no active flow.
    """
    flow: Optional[OnboardingFlow] = g.get("_onboarding_flow")
    if flow is None:
        return None
    reply, stage, done = flow.run_step(user_input, g)
    if done:
        g["_onboarding_flow"] = None
        g["_onboarding_stage"] = "complete"
        # Notify face recognizer to update embeddings
        try:
            from brain.face_recognizer import get_recognizer
            rec = get_recognizer(Path(g.get("BASE_DIR") or "."))
            rec.update_known_faces()
        except Exception:
            pass
    else:
        g["_onboarding_stage"] = stage
    return reply, stage, done


def get_onboarding_status(g: dict[str, Any]) -> dict[str, Any]:
    flow: Optional[OnboardingFlow] = g.get("_onboarding_flow")
    if flow is None:
        return {"active": False, "stage": None, "person_id": None, "stages": STAGES}
    stage_idx = STAGES.index(flow.stage)
    return {
        "active": True,
        "stage": flow.stage,
        "stage_index": stage_idx,
        "stage_count": len(STAGES),
        "stages": STAGES,
        "person_id": flow.person_id,
        "collected": {
            "name": flow.data.get("name"),
            "pronouns": flow.data.get("pronouns"),
            "photo_stages_done": list(flow.photos.keys()),
        },
    }


def refresh_profile(person_id: str, g: dict[str, Any]) -> dict[str, Any]:
    """
    Run abbreviated refresh flow for an existing person.
    Checks last_photo_date and quality_score.
    Returns dict with action taken.
    """
    base_dir = _base_dir(g)
    profile = _load_profile(person_id, base_dir)
    if not profile:
        return {"action": "not_found", "person_id": person_id}

    now = time.time()
    last_photo_raw = profile.get("last_photo_date") or ""
    quality = float(profile.get("quality_score") or 1.0)
    needs_photos = quality < 0.7
    try:
        import datetime as _dt
        last_photo_ts = _dt.datetime.fromisoformat(last_photo_raw).timestamp() if last_photo_raw else 0
        days_old = (now - last_photo_ts) / 86400
        needs_photos = needs_photos or days_old > 180
    except Exception:
        days_old = 999

    action = "refresh_prompted"
    if needs_photos:
        action = "retake_photos"
        flow = OnboardingFlow(person_id, base_dir, initial_name=profile.get("name"))
        flow.stage_index = STAGES.index("photo_front")
        flow._awaiting_ready = True
        g["_onboarding_flow"] = flow
        g["_onboarding_stage"] = "photo_front"

    # Update profile timestamp
    profile["updated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    _save_profile(person_id, profile, base_dir)
    return {"action": action, "person_id": person_id, "needs_photos": needs_photos, "days_old": round(days_old)}
