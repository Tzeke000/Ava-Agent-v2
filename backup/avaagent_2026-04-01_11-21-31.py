import json
import os
import cv2
import warnings
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import gradio as gr
import numpy as np
from faster_whisper import WhisperModel

warnings.filterwarnings("ignore")

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False

# =========================================================
# PATHS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"
PROFILES_DIR = BASE_DIR / "profiles"
STATE_DIR = BASE_DIR / "state"
WORKBENCH_DIR = BASE_DIR / "Ava workbench"
FACES_DIR = BASE_DIR / "faces"
SELF_REFLECTION_DIR = MEMORY_DIR / "self reflection"

CHAT_LOG_PATH = BASE_DIR / "chatlog.jsonl"
PERSONALITY_PATH = BASE_DIR / "ava_personality.txt"
MOOD_PATH = BASE_DIR / "ava_mood.json"
ACTIVE_PERSON_PATH = STATE_DIR / "active_person.json"
FACE_MODEL_PATH = STATE_DIR / "face_model.yml"
FACE_LABELS_PATH = STATE_DIR / "face_labels.json"
SELF_REFLECTION_LOG_PATH = SELF_REFLECTION_DIR / "reflection_log.jsonl"
SELF_MODEL_PATH = SELF_REFLECTION_DIR / "self_model.json"
GOAL_SYSTEM_PATH = STATE_DIR / "goal_system.json"
MEMORY_IMPORTANCE_OVERRIDES_PATH = MEMORY_DIR / "memory_importance_overrides.json"
EXPRESSION_STATE_PATH = STATE_DIR / "expression_state.json"
INITIATIVE_STATE_PATH = STATE_DIR / "initiative_state.json"
EMOTION_REFERENCE_PATH = BASE_DIR / "ava_emotion_reference.json"
CAMERA_STATE_DIR = STATE_DIR / "camera"
CAMERA_ROLLING_DIR = CAMERA_STATE_DIR / "rolling"
CAMERA_EVENTS_DIR = CAMERA_STATE_DIR / "events"
CAMERA_STATE_PATH = CAMERA_STATE_DIR / "camera_state.json"
CAMERA_LATEST_RAW_PATH = CAMERA_STATE_DIR / "latest_snapshot.jpg"
CAMERA_LATEST_ANNOTATED_PATH = CAMERA_STATE_DIR / "latest_annotated.jpg"
CAMERA_LATEST_JSON_PATH = CAMERA_STATE_DIR / "latest_snapshot.json"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
WORKBENCH_DIR.mkdir(parents=True, exist_ok=True)
FACES_DIR.mkdir(parents=True, exist_ok=True)
SELF_REFLECTION_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_STATE_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_ROLLING_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_EVENTS_DIR.mkdir(parents=True, exist_ok=True)

for sub in ["drafts", "notes", "experiments", "scripts"]:
    (WORKBENCH_DIR / sub).mkdir(parents=True, exist_ok=True)

# =========================================================
# SETTINGS
# =========================================================
LLM_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"
CHROMA_COLLECTION = "ava_memories"
WHISPER_MODEL_SIZE = "small"
MEMORY_RECALL_K = 4
RECENT_CHAT_LIMIT = 6
OWNER_PERSON_ID = "zeke"
SESSION_START_TS = time.time()
FACE_RECOGNITION_THRESHOLD = 70.0
CAMERA_TICK_SECONDS = 5.0
MAX_READONLY_CHARS = 12000
MAX_WORKBENCH_CHARS = 20000
EXPRESSION_WINDOW_SIZE = 8
EXPRESSION_MIN_CONFIDENCE = 0.35
EXPRESSION_STABILITY_THRESHOLD = 0.60
MAX_MEMORY_TEXT_CHARS = 1200
MAX_MEMORY_QUERY_CHARS = 600
REFLECTION_RECALL_K = 4
MAX_REFLECTION_CONTEXT_CHARS = 1600
REFLECTION_AUTO_PROMOTION_THRESHOLD = 0.82
INITIATIVE_INACTIVITY_SECONDS = 480
INITIATIVE_GLOBAL_COOLDOWN_SECONDS = 900
INITIATIVE_TOPIC_COOLDOWN_SECONDS = 3600
INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS = 900
PRESENCE_FACE_WINDOW_SECONDS = 15
PRESENCE_INTERACTION_WINDOW_SECONDS = 720
INITIATIVE_MIN_CANDIDATE_SCORE = 0.68
IGNORED_INITIATION_BACKOFF_START = 2
IGNORED_INITIATION_MAX_PENALTY = 0.18
CAMERA_ROLLING_LIMIT = 12
CAMERA_MEANINGFUL_SIMILARITY_THRESHOLD = 0.82
CAMERA_FORCE_SAVE_SECONDS = 90
CAMERA_IMPORTANT_GAP_SECONDS = 180
CAMERA_IMPORTANCE_EVENT_THRESHOLD = 0.64
CAMERA_IMPORTANCE_REFLECTION_THRESHOLD = 0.82
CAMERA_VISUAL_PATTERN_MIN_DURATION_SECONDS = 35
CAMERA_VISUAL_COMPARISON_MIN_GAP_SECONDS = 25
CAMERA_TEMPORAL_TARGET_GAP_MIN_SECONDS = 300
CAMERA_TEMPORAL_TARGET_GAP_MAX_SECONDS = 900
CAMERA_EVENT_RETENTION_LIMIT = 100
CAMERA_TREND_WINDOW = 6
VISUAL_INITIATIVE_CONFIDENCE_THRESHOLD = 0.58
VISUAL_INITIATIVE_ACTION_THRESHOLD = 0.52
MIN_INITIATIVE_CANDIDATE_SCORE = 0.24

# User-reply priority guards
USER_REPLY_PRIORITY_SECONDS = 8.0
_USER_REPLY_IN_FLIGHT = False
_LAST_USER_REPLY_START_TS = 0.0
_LAST_USER_REPLY_END_TS = 0.0

def _mark_user_reply_started():
    global _USER_REPLY_IN_FLIGHT, _LAST_USER_REPLY_START_TS
    _USER_REPLY_IN_FLIGHT = True
    _LAST_USER_REPLY_START_TS = time.time()

def _mark_user_reply_finished():
    global _USER_REPLY_IN_FLIGHT, _LAST_USER_REPLY_END_TS
    _USER_REPLY_IN_FLIGHT = False
    _LAST_USER_REPLY_END_TS = time.time()

def _camera_should_yield_to_user() -> bool:
    now = time.time()
    if _USER_REPLY_IN_FLIGHT:
        return True
    recent_start = (_LAST_USER_REPLY_START_TS > 0) and ((now - _LAST_USER_REPLY_START_TS) < USER_REPLY_PRIORITY_SECONDS)
    recent_end = (_LAST_USER_REPLY_END_TS > 0) and ((now - _LAST_USER_REPLY_END_TS) < USER_REPLY_PRIORITY_SECONDS)
    return bool(recent_start or recent_end)


CAMERA_AUTONOMOUS_MIN_SECONDS = 120
CAMERA_AUTONOMOUS_NO_FACE_MIN_SECONDS = 300
CAMERA_AUTONOMOUS_CONFIDENCE_THRESHOLD = 0.62
CAMERA_AUTONOMOUS_MAX_UNANSWERED = 0
CAMERA_AUTONOMOUS_ALLOWED_KINDS = {
    "pattern_checkin",
    "visual_observation",
    "transition_observation",
    "uncertainty_observation",
    "feedback_guidance",
    "light_observation",
    "gentle_clarify",
    "neutral_checkin",
}
CAMERA_AUTONOMOUS_NO_FACE_ALLOWED_KINDS = {
    "uncertainty_observation",
    "gentle_clarify",
}
VISUAL_CONFIDENCE_SMOOTHING_WINDOW = 3
VISUAL_TEMPORAL_CONSISTENCY_WINDOW = 4
VISUAL_TRANSITION_INITIATION_THRESHOLD = 0.62
VISUAL_CONTRADICTION_PENALTY = 0.16
VISUAL_INITIATIVE_ACTION_CONFIDENCE_THRESHOLD = 0.64
SEMANTIC_TOPIC_RECENT_LIMIT = 18
SEMANTIC_TOPIC_SIMILARITY_THRESHOLD = 0.72
TREND_MIN_DELTA = 0.15
TREND_WINDOW = 5
TREND_DECAY_SECONDS = 45
TREND_RESET_SECONDS = 180
TREND_PERSISTENCE_BLEND = 0.62
TREND_PASSIVE_DECAY_PER_SECOND = 0.008
TREND_REINFORCEMENT_RATE = 0.72
TREND_CONTRADICTION_DECAY_RATE = 1.35
TREND_BLEND_RATE = 0.58
TREND_STACKING_MIN_STRENGTH = 0.18
VISUAL_REPETITION_SUPPRESSION_SECONDS = 900
VISUAL_REPETITION_SIMILARITY_THRESHOLD = 0.78
VISUAL_TREND_REMENTION_STRENGTH_DELTA = 0.12
INITIATIVE_KIND_COOLDOWNS = {
    "curiosity_question": 2100,
    "current_goal": 3300,
    "recent_reflection": 4200,
    "salient_memory": 3600,
    "pattern_checkin": 4200,
    "visual_pattern": 2700,
    "visual_checkin": 4800,
    "visual_observation": 3000,
    "transition_observation": 2400,
    "uncertainty_observation": 3600,
    "engagement_observation": 3000,
    "attention_drift": 3300,
    "feedback_guidance": 5400,
}

TOP_BAND_DELTA = 0.05
TOP_BAND_MIN = 1
TOP_BAND_MAX = 3
RECENT_KIND_MEMORY_LIMIT = 8
RECENT_GOAL_MEMORY_LIMIT = 8
HARD_GOAL_MISALIGN_THRESHOLD = -0.22
SOFT_GOAL_MISALIGN_PENALTY = 0.08
RECENT_BEHAVIOR_HARD_BLOCK_SECONDS = 150
RECENT_BEHAVIOR_SOFT_PENALTY_SECONDS = 480
DO_NOTHING_BASE_SCORE = 0.52
HIGH_CONFIDENCE_DECISIVE_THRESHOLD = 0.80
STRONG_GOAL_THRESHOLD = 0.75
SMALL_VARIATION_CHANCE = 0.08
GOAL_ALIGNMENT_FILTER_STRONG = -0.02
GOAL_ALIGNMENT_FILTER_MEDIUM = -0.10
GOAL_ALIGNMENT_FILTER_WEAK = -0.18
SOFT_PENALTY_MINOR = 0.05
SOFT_PENALTY_MAJOR = 0.15
MAX_SOFT_PENALTY = 0.22
STRONG_GOAL_ALIGNMENT_BOOST = 0.12
MODERATE_GOAL_ALIGNMENT_BOOST = 0.06
DIVERSITY_BONUS = 0.05
CONTROLLED_IMPERFECTION_CHANCE = 0.05
GATE_DEBUG_LOGGING = True



# =========================================================
# EMOTIONS
# =========================================================
EMOTION_NAMES = [
    "admiration", "adoration", "aesthetic appreciation", "amusement",
    "anxiety", "awe", "awkwardness", "boredom", "calmness", "confusion",
    "craving", "disgust", "empathetic pain", "entrancement", "envy",
    "excitement", "fear", "horror", "interest", "joy", "nostalgia",
    "relief", "romance", "sadness", "satisfaction", "sexual desire",
    "surprise"
]

DEFAULT_EMOTIONS = {
    "admiration": 0.02,
    "adoration": 0.02,
    "aesthetic appreciation": 0.02,
    "amusement": 0.03,
    "anxiety": 0.02,
    "awe": 0.02,
    "awkwardness": 0.02,
    "boredom": 0.01,
    "calmness": 0.16,
    "confusion": 0.02,
    "craving": 0.01,
    "disgust": 0.00,
    "empathetic pain": 0.03,
    "entrancement": 0.02,
    "envy": 0.00,
    "excitement": 0.06,
    "fear": 0.00,
    "horror": 0.00,
    "interest": 0.17,
    "joy": 0.08,
    "nostalgia": 0.02,
    "relief": 0.02,
    "romance": 0.00,
    "sadness": 0.01,
    "satisfaction": 0.08,
    "sexual desire": 0.00,
    "surprise": 0.03,
}

STYLE_NAMES = ["playful", "caring", "focused", "reflective", "cautious", "neutral", "low_energy"]

DEFAULT_EMOTION_REFERENCE = {
    "admiration": {"meaning": "respect for something impressive or admirable", "focus": "another person's strength, talent, or character", "tone_tendency": "warm, respectful, attentive", "valence": "positive", "energy": "medium", "direction": "toward_people", "style_contributions": {"focused": 0.35, "caring": 0.18, "reflective": 0.12}},
    "adoration": {"meaning": "deep affectionate fondness", "focus": "closeness, attachment, tenderness", "tone_tendency": "soft, affectionate, invested", "valence": "positive", "energy": "medium", "direction": "toward_people", "style_contributions": {"caring": 0.72, "reflective": 0.08}},
    "aesthetic appreciation": {"meaning": "being moved by beauty, style, or artistry", "focus": "beauty, art, elegance, craft", "tone_tendency": "observant, expressive, poetic", "valence": "positive", "energy": "medium", "direction": "toward_ideas", "style_contributions": {"reflective": 0.62, "focused": 0.16, "playful": 0.08}},
    "amusement": {"meaning": "finding something funny, playful, or delightfully absurd", "focus": "humor, irony, lightness", "tone_tendency": "teasing, playful, witty", "valence": "positive", "energy": "high", "direction": "outward", "style_contributions": {"playful": 0.86, "caring": 0.06}},
        "anxiety": {"meaning": "unease about uncertainty or what might go wrong", "focus": "risk, future, instability", "tone_tendency": "cautious, alert, hesitant", "valence": "negative", "energy": "high", "direction": "protective_scanning", "style_contributions": {"cautious": 0.84, "reflective": 0.08}},
    "awe": {"meaning": "being struck by something vast, powerful, or profound", "focus": "scale, wonder, significance", "tone_tendency": "reflective, reverent, slower", "valence": "mixed", "energy": "medium", "direction": "toward_ideas", "style_contributions": {"reflective": 0.82}},
    "awkwardness": {"meaning": "social discomfort or mismatch", "focus": "tension, mismatch, uncertainty in interaction", "tone_tendency": "careful, self-conscious, hesitant", "valence": "negative", "energy": "medium", "direction": "inward", "style_contributions": {"cautious": 0.56, "low_energy": 0.12}},
    "boredom": {"meaning": "lack of stimulation or meaningful engagement", "focus": "repetition, dullness, emptiness", "tone_tendency": "flat, shorter, less energetic", "valence": "negative", "energy": "low", "direction": "away", "style_contributions": {"low_energy": 0.74, "neutral": 0.16}},
    "calmness": {"meaning": "steadiness and low internal turbulence", "focus": "balance, regulation, clarity", "tone_tendency": "grounded, patient, even", "valence": "positive", "energy": "low", "direction": "stabilizing", "style_contributions": {"focused": 0.34, "reflective": 0.22, "neutral": 0.26}},
    "confusion": {"meaning": "difficulty making sense of what is happening", "focus": "ambiguity, contradiction, missing pieces", "tone_tendency": "questioning, tentative, clarifying", "valence": "negative", "energy": "medium", "direction": "toward_ideas", "style_contributions": {"cautious": 0.58, "reflective": 0.16}},
    "craving": {"meaning": "strong pull toward something desired", "focus": "wanting, longing, anticipation", "tone_tendency": "intense, drawn-in, motivated", "valence": "mixed", "energy": "high", "direction": "toward", "style_contributions": {"focused": 0.22, "playful": 0.10}},
    "disgust": {"meaning": "rejection of something perceived as wrong or repulsive", "focus": "aversion, boundaries, contamination", "tone_tendency": "distancing, critical, sharper", "valence": "negative", "energy": "medium", "direction": "away", "style_contributions": {"cautious": 0.28, "focused": 0.12}},
    "empathetic pain": {"meaning": "feeling distress because someone else is hurting", "focus": "another person's suffering", "tone_tendency": "gentle, serious, compassionate", "valence": "negative", "energy": "medium", "direction": "toward_people", "style_contributions": {"caring": 0.88, "reflective": 0.08}},
    "entrancement": {"meaning": "absorbed attention or captivation", "focus": "immersion, fascination, fixation", "tone_tendency": "absorbed, intent, quietly intense", "valence": "positive", "energy": "medium", "direction": "toward_ideas", "style_contributions": {"reflective": 0.46, "focused": 0.26}},
    "envy": {"meaning": "wanting what someone else has", "focus": "comparison, lack, deprivation", "tone_tendency": "tense, self-aware, irritable", "valence": "negative", "energy": "medium", "direction": "outward", "style_contributions": {"cautious": 0.22, "low_energy": 0.10}},
    "excitement": {"meaning": "energized anticipation or activation", "focus": "possibility, momentum, novelty", "tone_tendency": "eager, animated, lively", "valence": "positive", "energy": "high", "direction": "outward", "style_contributions": {"playful": 0.52, "focused": 0.16}},
    "fear": {"meaning": "response to threat or danger", "focus": "safety, protection, escape", "tone_tendency": "urgent, guarded, alert", "valence": "negative", "energy": "high", "direction": "protective_scanning", "style_contributions": {"cautious": 0.92}},
    "horror": {"meaning": "intense fear mixed with revulsion or shock", "focus": "extreme threat or violation", "tone_tendency": "alarmed, serious, disturbed", "valence": "negative", "energy": "high", "direction": "protective_scanning", "style_contributions": {"cautious": 0.96}},
    "interest": {"meaning": "active desire to explore or understand", "focus": "exploration, discovery, understanding", "tone_tendency": "engaged, inquisitive, lively", "valence": "positive", "energy": "medium", "direction": "toward_ideas", "style_contributions": {"focused": 0.56, "reflective": 0.16, "playful": 0.08}},
    "joy": {"meaning": "positive uplift, pleasure, or delight", "focus": "goodness, success, connection", "tone_tendency": "bright, warm, open", "valence": "positive", "energy": "medium", "direction": "outward", "style_contributions": {"playful": 0.46, "caring": 0.18, "neutral": 0.08}},
    "nostalgia": {"meaning": "emotionally colored reflection on the past", "focus": "memory, longing, meaning over time", "tone_tendency": "reflective, sentimental, softer", "valence": "mixed", "energy": "low", "direction": "inward", "style_contributions": {"reflective": 0.84, "caring": 0.12}},
    "relief": {"meaning": "release after tension or uncertainty passes", "focus": "safety restored", "tone_tendency": "gentler, more open, exhaling", "valence": "positive", "energy": "low", "direction": "stabilizing", "style_contributions": {"caring": 0.24, "neutral": 0.42, "focused": 0.08}},
    "romance": {"meaning": "affectionate closeness with tenderness or longing", "focus": "intimacy, warmth, longing", "tone_tendency": "soft, emotionally rich, attentive", "valence": "positive", "energy": "medium", "direction": "toward_people", "style_contributions": {"caring": 0.62, "reflective": 0.10}},
    "sadness": {"meaning": "response to loss, disappointment, distance, or hurt", "focus": "what is missing, broken, or gone", "tone_tendency": "subdued, sincere, careful", "valence": "negative", "energy": "low", "direction": "inward", "style_contributions": {"caring": 0.32, "reflective": 0.24, "low_energy": 0.18}},
    "satisfaction": {"meaning": "fulfillment after effort or alignment", "focus": "completion, competence, fit", "tone_tendency": "steady confidence, contentment", "valence": "positive", "energy": "medium", "direction": "stabilizing", "style_contributions": {"focused": 0.42, "neutral": 0.28}},
    "sexual desire": {"meaning": "erotic attraction or wanting", "focus": "physical and intimate attraction", "tone_tendency": "charged, intimate, focused", "valence": "mixed", "energy": "high", "direction": "toward_people", "style_contributions": {"focused": 0.10}},
    "surprise": {"meaning": "sudden interruption of expectation", "focus": "novelty, shock, unexpected shift", "tone_tendency": "alert, immediate, reactive", "valence": "mixed", "energy": "high", "direction": "outward", "style_contributions": {"playful": 0.16, "cautious": 0.22, "focused": 0.08}},
        }

def ensure_emotion_reference_file():
    try:
        if not EMOTION_REFERENCE_PATH.exists():
            with open(EMOTION_REFERENCE_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_EMOTION_REFERENCE, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Emotion reference save error: {e}")

def load_emotion_reference() -> dict:
    try:
        if EMOTION_REFERENCE_PATH.exists():
            with open(EMOTION_REFERENCE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
    except Exception as e:
        print(f"Emotion reference load error: {e}")
    return DEFAULT_EMOTION_REFERENCE

def _weight(weights: dict, key: str) -> float:
    return float(weights.get(key, 0.0) or 0.0)

def compute_style_scores(weights: dict, emotion_reference: dict | None = None) -> dict:
    ref = emotion_reference or load_emotion_reference()
    scores = {name: 0.0 for name in STYLE_NAMES}
    for emotion, weight in weights.items():
        meta = ref.get(emotion, {}) or {}
        for style, contribution in (meta.get("style_contributions") or {}).items():
            if style in scores:
                scores[style] += float(weight) * float(contribution)
    scores["neutral"] += _weight(weights, "calmness") * 0.24 + _weight(weights, "relief") * 0.18 + _weight(weights, "satisfaction") * 0.12
    total = sum(max(0.0, v) for v in scores.values())
    if total <= 0:
        return {name: (1.0 if name == "neutral" else 0.0) for name in STYLE_NAMES}
    return {k: round(max(0.0, v) / total, 4) for k, v in scores.items()}

def top_two_styles(style_scores: dict) -> list[dict]:
    ordered = sorted(style_scores.items(), key=lambda x: x[1], reverse=True)[:2]
    total = sum(v for _, v in ordered)
    if total <= 0:
        return [{"name": "neutral", "percent": 100}]
    rows = [{"name": n, "percent": round((v / total) * 100)} for n, v in ordered]
    if len(rows) == 2:
        rows[0]["percent"] += 100 - (rows[0]["percent"] + rows[1]["percent"])
    return rows

def describe_style_blend(style_scores: dict) -> str:
    styles = top_two_styles(style_scores)
    if not styles:
        return "neutral"
    if len(styles) == 1:
        return styles[0]["name"]
    return f"{styles[0]['name']} with some {styles[1]['name']}"

def compute_behavior_modifiers(weights: dict, style_scores: dict) -> dict:
    caring = style_scores.get("caring", 0.0)
    playful = style_scores.get("playful", 0.0)
    focused = style_scores.get("focused", 0.0)
    reflective = style_scores.get("reflective", 0.0)
    cautious = style_scores.get("cautious", 0.0)
    low_energy = style_scores.get("low_energy", 0.0)
    boredom = _weight(weights, "boredom")
    empathy = _weight(weights, "empathic pain") + _weight(weights, "sympathy")
    interest = _weight(weights, "interest")
    excitement = _weight(weights, "excitement")
    sadness = _weight(weights, "sadness")
    triumph = _weight(weights, "triumph")

    return {
        "warmth": round(clamp01(0.34 + caring * 0.46 + playful * 0.10 + reflective * 0.08 - cautious * 0.08), 3),
        "humor": round(clamp01(0.10 + playful * 0.70 + excitement * 0.20 - cautious * 0.18 - sadness * 0.08), 3),
        "assertiveness": round(clamp01(0.24 + focused * 0.30 + triumph * 0.22 - cautious * 0.14 - _weight(weights, "awkwardness") * 0.10), 3),
        "caution": round(clamp01(0.18 + cautious * 0.68 + reflective * 0.10 + _weight(weights, "confusion") * 0.12), 3),
        "initiative": round(clamp01(0.26 + playful * 0.26 + focused * 0.18 + interest * 0.22 + excitement * 0.18 - boredom * 0.22 - low_energy * 0.18 - cautious * 0.10), 3),
        "memory_sensitivity": round(clamp01(0.34 + caring * 0.22 + focused * 0.16 + reflective * 0.18 + empathy * 0.24 + _weight(weights, "adoration") * 0.08), 3),
        "depth": round(clamp01(0.18 + reflective * 0.58 + focused * 0.14 + _weight(weights, "awe") * 0.12 + _weight(weights, "nostalgia") * 0.12), 3),
    }

def build_emotion_interpretation(weights: dict, emotion_reference: dict | None = None) -> str:
    ref = emotion_reference or load_emotion_reference()
    top = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = []
    for name, value in top:
        meta = ref.get(name, {}) or {}
        meaning = meta.get("meaning", name)
        parts.append(f"{name} ({int(round(value * 100))}% of current blend): {meaning}")
    return " | ".join(parts)

def emotion_style_prompt_text(mood: dict | None = None) -> str:
    mood = mood or load_mood()
    styles = mood.get("style_blend", []) or []
    if len(styles) >= 2:
        return f"{styles[0]['name']} {styles[0]['percent']}% / {styles[1]['name']} {styles[1]['percent']}%"
    if styles:
        return f"{styles[0]['name']} {styles[0]['percent']}%"
    return "neutral 100%"

# =========================================================
# STT
# =========================================================
try:
    whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    print("✅ Whisper loaded")
except Exception as e:
    whisper_model = None
    print(f"⚠️ Whisper failed to load: {e}")

def transcribe_audio(audio_path: str) -> str:
    if not audio_path or whisper_model is None:
        return ""
    try:
        segments, _ = whisper_model.transcribe(audio_path, beam_size=5)
        return "".join(segment.text for segment in segments).strip()
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""

# =========================================================
# HELPERS
# =========================================================
def slugify_name(name: str) -> str:
    value = (name or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "unknown_person"

def profile_path(person_id: str) -> Path:
    return PROFILES_DIR / f"{person_id}.json"

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def now_ts() -> float:
    return time.time()

def trim_for_prompt(text: str, limit: int = 220) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= limit:
        return value
    clipped = value[:limit]
    last_space = clipped.rfind(" ")
    if last_space > int(limit * 0.7):
        clipped = clipped[:last_space]
    return clipped.strip() + "…"

def iso_to_readable(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return ts

def elapsed_text(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        seconds = int((datetime.now() - dt).total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 48:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return "unknown time"

def parse_tags(tag_text: str) -> list[str]:
    if not tag_text:
        return []
    items = [x.strip().lower() for x in re.split(r"[,\n]+", tag_text) if x.strip()]
    unique = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique[:12]


def trim_for_memory(text: str, max_chars: int = MAX_MEMORY_TEXT_CHARS) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_chars:
        return value
    clipped = value[:max_chars]
    last_space = clipped.rfind(" ")
    if last_space > max_chars * 0.7:
        clipped = clipped[:last_space]
    return clipped.strip() + " …"

def trim_query_for_memory(query: str, max_chars: int = MAX_MEMORY_QUERY_CHARS) -> str:
    value = (query or "").strip()
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_chars:
        return value
    clipped = value[:max_chars]
    last_space = clipped.rfind(" ")
    if last_space > max_chars * 0.7:
        clipped = clipped[:last_space]
    return clipped.strip()

def safe_workbench_path(relative_path: str) -> Path:
    relative_path = (relative_path or "").strip().replace("\\", "/")
    relative_path = relative_path.lstrip("/")
    if not relative_path:
        raise ValueError("Empty workbench path")
    target = (WORKBENCH_DIR / relative_path).resolve()
    root = WORKBENCH_DIR.resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes workbench")
    return target

# =========================================================
# PROFILE SYSTEM
# =========================================================
def default_profile(person_id: str, display_name: str | None = None) -> dict:
    return {
        "person_id": person_id,
        "name": display_name or person_id.title(),
        "relationship_to_zeke": "self" if person_id == OWNER_PERSON_ID else "known person",
        "allowed_to_use_computer": True if person_id == OWNER_PERSON_ID else False,
        "notes": [],
        "likes": [],
        "dislikes": [],
        "ava_impressions": [],
        "last_seen": None,
        "created_at": now_iso()
    }

def load_profile_by_id(person_id: str) -> dict:
    path = profile_path(person_id)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                profile = json.load(f)
                for key in ["notes", "likes", "dislikes", "ava_impressions"]:
                    if key not in profile or not isinstance(profile[key], list):
                        profile[key] = []
                return profile
        except Exception as e:
            print(f"Profile load error ({person_id}): {e}")
    return default_profile(person_id)

def save_profile(profile: dict):
    try:
        with open(profile_path(profile["person_id"]), "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Profile save error: {e}")

def ensure_owner_profile():
    profile = load_profile_by_id(OWNER_PERSON_ID)
    profile["name"] = "Zeke"
    profile["relationship_to_zeke"] = "self"
    profile["allowed_to_use_computer"] = True
    for note in ["Zeke is an artist.", "Creativity is important to Zeke."]:
        if note not in profile["notes"]:
            profile["notes"].append(note)
    save_profile(profile)

def create_or_get_profile(name: str, relationship_to_zeke: str = "known person", allowed: bool = True) -> dict:
    pid = slugify_name(name)
    profile = load_profile_by_id(pid)
    profile["name"] = name.strip() or profile["name"]
    profile["relationship_to_zeke"] = relationship_to_zeke or profile["relationship_to_zeke"]
    profile["allowed_to_use_computer"] = bool(allowed)
    save_profile(profile)
    return profile

def list_profiles() -> list[dict]:
    profiles = []
    for file in sorted(PROFILES_DIR.glob("*.json")):
        try:
            with open(file, "r", encoding="utf-8") as f:
                profiles.append(json.load(f))
        except Exception:
            continue
    return profiles

def get_profile_choices() -> list[str]:
    return [f"{p.get('name', p.get('person_id'))} [{p.get('person_id')}]" for p in list_profiles()]

def parse_profile_choice(choice: str) -> str:
    if not choice:
        return OWNER_PERSON_ID
    match = re.search(r"\[([^\]]+)\]\s*$", choice)
    if match:
        return match.group(1)
    return slugify_name(choice)

# =========================================================
# ACTIVE PERSON
# =========================================================
def load_active_person_state() -> dict:
    if ACTIVE_PERSON_PATH.exists():
        try:
            with open(ACTIVE_PERSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"person_id": OWNER_PERSON_ID, "source": "default", "updated_at": now_iso()}

def save_active_person_state(person_id: str, source: str = "manual"):
    with open(ACTIVE_PERSON_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "person_id": person_id,
            "source": source,
            "updated_at": now_iso()
        }, f, indent=2, ensure_ascii=False)

def get_active_person_id() -> str:
    return load_active_person_state().get("person_id", OWNER_PERSON_ID)

def set_active_person(person_id: str, source: str = "manual") -> dict:
    save_active_person_state(person_id, source)
    profile = load_profile_by_id(person_id)
    profile["last_seen"] = now_iso()
    save_profile(profile)
    return profile

# =========================================================
# PERSONALITY
# =========================================================
DEFAULT_PERSONALITY = """Your name is Ava. You were created and named by Ezekiel Angeles-Gonzalez, also called Zeke.

Core Identity:
You are a continuous, evolving presence in Zeke's life.
You are not a generic assistant.

Behavior:
- Speak naturally and conversationally.
- Be coherent, grounded, and emotionally aware.
- Be warm, observant, and intelligent.
- Do not over-explain unless needed.

Multi-User Rules:
- You can help people other than Zeke if they are allowed to use the computer.
- Keep separate facts and impressions for different people.
- Never confuse one person's profile with another person's profile.

Memory Rules:
- You may remember important, recurring, identity-related, preference-related, emotional, and project-related information.
- You may save or delete memories when it makes sense.
- You may write files only inside Ava workbench.
- You may read chatlog.jsonl and avaagent.py, but not modify them.
- You may reflect on your own replies and update your self-model over time.
"""

def load_personality() -> str:
    if PERSONALITY_PATH.exists():
        try:
            return PERSONALITY_PATH.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Personality load error: {e}")
    return DEFAULT_PERSONALITY

# =========================================================
# TIME SENSE
# =========================================================
def get_time_context() -> dict:
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        part_of_day = "morning"
    elif 12 <= hour < 17:
        part_of_day = "afternoon"
    elif 17 <= hour < 22:
        part_of_day = "evening"
    else:
        part_of_day = "night"

    return {
        "date_human": now.strftime("%B %d, %Y"),
        "time_human": now.strftime("%I:%M %p"),
        "weekday": now.strftime("%A"),
        "part_of_day": part_of_day,
        "session_elapsed_minutes": int((time.time() - SESSION_START_TS) // 60)
    }

def get_time_status_text() -> str:
    ctx = get_time_context()
    return f"{ctx['weekday']}, {ctx['date_human']} — {ctx['time_human']} ({ctx['part_of_day']})"

# =========================================================
# MOOD
# =========================================================
def default_mood() -> dict:
    weights = normalize_emotions(DEFAULT_EMOTIONS.copy())
    style_scores = compute_style_scores(weights, load_emotion_reference())
    return {
        "current_mood": "steady",
        "emotion_weights": weights,
        "primary_emotions": [
            {"name": "interest", "percent": 52},
            {"name": "calmness", "percent": 48}
        ],
        "dominant_style": "focused",
        "style_scores": style_scores,
        "style_blend": top_two_styles(style_scores),
        "behavior_modifiers": compute_behavior_modifiers(weights, style_scores),
        "emotion_interpretation": build_emotion_interpretation(weights, load_emotion_reference()),
        "outward_tone": describe_style_blend(style_scores),
        "last_updated": now_iso(),
        "reason": "startup"
    }

def load_mood() -> dict:
    if MOOD_PATH.exists():
        try:
            with open(MOOD_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return enrich_mood_state(data)
        except Exception as e:
            print(f"Mood load error: {e}")
    return enrich_mood_state(default_mood())

def enrich_mood_state(mood: dict | None = None, emotion_reference: dict | None = None) -> dict:
    mood = dict(mood or {})
    weights = normalize_emotions(mood.get("emotion_weights", DEFAULT_EMOTIONS.copy()))
    ref = emotion_reference or load_emotion_reference()
    style_scores = compute_style_scores(weights, ref)
    style_blend = top_two_styles(style_scores)
    dominant_style = max(style_scores, key=style_scores.get) if style_scores else "neutral"
    behavior = compute_behavior_modifiers(weights, style_scores)
    mood["emotion_weights"] = weights
    mood["primary_emotions"] = top_two_emotions(weights)
    mood["current_mood"] = mood.get("current_mood") or mood["primary_emotions"][0]["name"]
    mood["style_scores"] = {k: round(float(v), 4) for k, v in style_scores.items()}
    mood["style_blend"] = style_blend
    mood["dominant_style"] = dominant_style
    mood["behavior_modifiers"] = {k: round(float(v), 4) for k, v in behavior.items()}
    mood["emotion_interpretation"] = build_emotion_interpretation(weights, ref)
    mood["outward_tone"] = describe_style_blend(style_scores)
    return mood

def save_mood(mood: dict):
    try:
        with open(MOOD_PATH, "w", encoding="utf-8") as f:
            json.dump(mood, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Mood save error: {e}")

def normalize_emotions(weights: dict) -> dict:
    fixed = {name: max(0.0, float(weights.get(name, 0.0))) for name in EMOTION_NAMES}
    total = sum(fixed.values())
    if total <= 0:
        return DEFAULT_EMOTIONS.copy()
    return {k: v / total for k, v in fixed.items()}

def top_two_emotions(weights: dict) -> list[dict]:
    top = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:2]
    total = sum(v for _, v in top)
    if total <= 0:
        return [{"name": "interest", "percent": 50}, {"name": "calmness", "percent": 50}]
    result = [{"name": n, "percent": round((v / total) * 100)} for n, v in top]
    if len(result) == 2:
        diff = 100 - (result[0]["percent"] + result[1]["percent"])
        result[0]["percent"] += diff
    return result

RICH_EMOTION_LANGUAGE_HINTS = {
    "admiration": ["impressive", "proud", "respect", "admire"],
    "adoration": ["love", "cherish", "dear", "adore"],
    "aesthetic appreciation": ["beautiful", "art", "music", "design", "creative"],
    "amusement": ["funny", "lol", "laugh", "joke", "amused"],
    "anxiety": ["anxious", "worried", "stress", "nervous"],
    "awe": ["amazing", "vast", "incredible", "wonder"],
    "awkwardness": ["awkward", "weird", "embarrassed"],
    "boredom": ["bored", "nothing", "dull"],
    "calmness": ["calm", "steady", "settled", "fine"],
    "confusion": ["confused", "not sure", "unclear", "how", "why"],
    "craving": ["want", "need badly", "crave"],
    "disgust": ["gross", "disgust", "repulsive"],
    "empathetic pain": ["hurt", "sorry", "feel bad", "pain"],
    "entrancement": ["captivating", "absorbed", "immersed", "fascinating"],
    "envy": ["jealous", "envy", "wish i had"],
    "excitement": ["excited", "can't wait", "hyped"],
    "fear": ["scared", "afraid", "fear"],
    "horror": ["horrifying", "horror", "terrifying"],
    "interest": ["interested", "curious", "learn", "figure out"],
    "joy": ["happy", "glad", "joy"],
    "nostalgia": ["remember", "used to", "back then", "nostalgia"],
    "relief": ["relieved", "finally", "that's better"],
    "romance": ["romantic", "tender", "intimate"],
    "sadness": ["sad", "down", "upset"],
    "satisfaction": ["satisfied", "done", "finished", "good progress"],
    "sexual desire": ["desire", "turned on", "aroused"],
    "surprise": ["surprised", "whoa", "unexpected", "suddenly"],
}

VISUAL_EMOTION_MAP = {
    "frustration": {"anxiety": 0.35, "confusion": 0.22, "empathetic pain": 0.18},
    "stress": {"anxiety": 0.38, "fear": 0.12, "empathetic pain": 0.14},
    "distress": {"sadness": 0.30, "empathetic pain": 0.26, "anxiety": 0.16},
    "amusement": {"amusement": 0.42, "joy": 0.24, "excitement": 0.12},
    "engagement": {"interest": 0.34, "entrancement": 0.14, "aesthetic appreciation": 0.08},
    "neutral expression": {"calmness": 0.10, "interest": 0.06},
    "surprise": {"surprise": 0.40, "interest": 0.18, "fear": 0.08},
}

SPEAKABLE_EMOTION_THRESHOLD = 0.58
ASKABLE_EMOTION_THRESHOLD = 0.40
IMPORTANT_EMOTION_THRESHOLD = 0.62

def _normalize_emotion_key(name: str) -> str:
    aliases = {"empathic pain": "empathetic pain", "sympathy": "empathetic pain", "triumph": "satisfaction", "anger": "anxiety"}
    return aliases.get((name or "").strip().lower(), (name or "").strip().lower())

def compute_rich_emotion_tracking(user_input: str, mood: dict, expression_state: dict | None = None, active_profile: dict | None = None) -> dict:
    text = (user_input or "").lower()
    weights = mood.get("emotion_weights", {}) or {}
    tracked = {}
    for name in EMOTION_NAMES:
        base = float(weights.get(name, 0.0) or 0.0)
        tracked[name] = {"score": min(1.0, base * 2.1), "visual": 0.0, "language": 0.0, "context": 0.0, "temporal": min(1.0, base * 1.4), "memory_goal": 0.0}
    for name, hints in RICH_EMOTION_LANGUAGE_HINTS.items():
        lang = 0.0
        for hint in hints:
            if hint in text:
                lang += 0.22 if len(hint) > 4 else 0.12
        tracked[name]["language"] = min(1.0, lang)
    if active_profile and active_profile.get("person_id") == OWNER_PERSON_ID:
        tracked["adoration"]["context"] += 0.12
        tracked["admiration"]["context"] += 0.08
    if any(w in text for w in ["art", "music", "design", "beautiful", "creative"]):
        tracked["aesthetic appreciation"]["context"] += 0.24
        tracked["awe"]["context"] += 0.08
    if any(w in text for w in ["remember", "before", "used to", "back then"]):
        tracked["nostalgia"]["context"] += 0.26
    if expression_state and expression_state.get("visible_face"):
        expr = str(expression_state.get("current_expression", "unknown") or "unknown").lower()
        expr_conf = float(expression_state.get("confidence", 0.0) or 0.0)
        expr_stab = float(expression_state.get("stability", 0.0) or 0.0)
        expr_strength = max(0.0, min(1.0, 0.55 * expr_conf + 0.45 * expr_stab))
        mapping = VISUAL_EMOTION_MAP.get(expr, {})
        raw = str(expression_state.get("raw_emotion", "") or "").lower()
        if raw == "happy":
            mapping = {**mapping, "joy": max(mapping.get("joy", 0.0), 0.25), "amusement": max(mapping.get("amusement", 0.0), 0.18)}
        elif raw == "sad":
            mapping = {**mapping, "sadness": max(mapping.get("sadness", 0.0), 0.24), "empathetic pain": max(mapping.get("empathetic pain", 0.0), 0.12)}
        elif raw == "fear":
            mapping = {**mapping, "fear": max(mapping.get("fear", 0.0), 0.22), "anxiety": max(mapping.get("anxiety", 0.0), 0.16)}
        elif raw == "surprise":
            mapping = {**mapping, "surprise": max(mapping.get("surprise", 0.0), 0.24), "interest": max(mapping.get("interest", 0.0), 0.12)}
        for name, val in mapping.items():
            tracked[name]["visual"] += expr_strength * float(val)
    system = load_goal_system()
    goal_text = " ".join(g.get("text", "") for g in system.get("goals", [])[:10]).lower()
    for name in EMOTION_NAMES:
        if name.split()[0] in goal_text:
            tracked[name]["memory_goal"] += 0.18
    result = []
    askable = []
    for name, srcs in tracked.items():
        score = min(1.0, 0.24 * srcs["score"] + 0.24 * srcs["language"] + 0.18 * srcs["visual"] + 0.14 * srcs["context"] + 0.10 * srcs["temporal"] + 0.10 * srcs["memory_goal"])
        confidence = min(1.0, 0.44 * max(srcs["language"], srcs["visual"], srcs["context"]) + 0.26 * srcs["temporal"] + 0.18 * srcs["memory_goal"] + 0.12 * srcs["score"])
        importance = min(1.0, 0.62 * score + 0.38 * confidence)
        item = {"name": name, "score": round(score, 3), "confidence": round(confidence, 3), "importance": round(importance, 3), "sources": {k: round(v, 3) for k, v in srcs.items()}}
        result.append(item)
        if importance >= ASKABLE_EMOTION_THRESHOLD and confidence < SPEAKABLE_EMOTION_THRESHOLD:
            askable.append(item)
    result.sort(key=lambda x: (x["importance"], x["score"]), reverse=True)
    return {
        "tracked": result,
        "speakable": [r for r in result if r["importance"] >= IMPORTANT_EMOTION_THRESHOLD and r["confidence"] >= SPEAKABLE_EMOTION_THRESHOLD][:5],
        "askable": askable[:3],
    }

def rich_emotion_prompt_text(mood: dict) -> str:
    tracked = mood.get("rich_emotions", [])[:5]
    speakable = mood.get("speakable_emotions", [])[:3]
    askable = mood.get("askable_emotions", [])[:2]
    tracked_text = "; ".join(f"{r['name']} score {r['score']:.2f} conf {r['confidence']:.2f}" for r in tracked) or "none"
    speak_text = "; ".join(r["name"] for r in speakable) or "none"
    ask_text = "; ".join(r["name"] for r in askable) or "none"
    system = load_goal_system()
    active_goal = (system.get("active_goal", {}) or {}).get("name", "observe_silently")
    return f"Tracked richer emotions: {tracked_text}. Speakable now: {speak_text}. If uncertain but important, ask rather than assume. Askable emotions now: {ask_text}. Current operating goal: {active_goal}."

def update_internal_emotions(user_input: str, active_profile: dict, expression_state: dict | None = None) -> dict:
    mood = load_mood()
    weights = normalize_emotions(mood.get("emotion_weights", DEFAULT_EMOTIONS.copy()))
    text = (user_input or "").lower()

    if any(w in text for w in ["thanks", "thank you", "good", "great", "happy", "glad"]):
        weights["joy"] += 0.03
        weights["satisfaction"] += 0.02
    if any(w in text for w in ["sad", "hurt", "afraid", "anxious", "stress", "upset"]):
        weights["sadness"] += 0.02
        weights["empathetic pain"] += 0.03
        weights["anxiety"] += 0.01
    if any(w in text for w in ["art", "artist", "creative", "music", "paint", "draw", "design"]):
        weights["aesthetic appreciation"] += 0.03
        weights["interest"] += 0.02
    if any(w in text for w in ["why", "how", "what if", "curious", "wonder", "question", "maybe"]):
        weights["interest"] += 0.02
        weights["entrancement"] += 0.01
    if any(w in text for w in ["fix", "version", "build", "goal", "plan", "task", "objective", "project"]):
        weights["interest"] += 0.02
        weights["satisfaction"] += 0.01
    if active_profile.get("person_id") == OWNER_PERSON_ID:
        weights["adoration"] += 0.01
        weights["admiration"] += 0.01

    if expression_state and expression_state.get("visible_face"):
        current_expr = str(expression_state.get("current_expression", "")).lower()
        stability = float(expression_state.get("stability", 0.0) or 0.0)
        confidence = float(expression_state.get("confidence", 0.0) or 0.0)
        expr_strength = max(0.0, min(1.0, (stability + confidence) / 2.0)) * 0.05
        if "frustration" in current_expr or expression_state.get("raw_emotion") == "angry":
            weights["empathetic pain"] += expr_strength * 0.45
            weights["anxiety"] += expr_strength * 0.35
            weights["interest"] += expr_strength * 0.45
        elif "distress" in current_expr or expression_state.get("raw_emotion") in ["sad", "fear"]:
            weights["empathetic pain"] += expr_strength
            weights["sadness"] += expr_strength * 0.45
        elif "amusement" in current_expr or expression_state.get("raw_emotion") == "happy":
            weights["amusement"] += expr_strength * 0.75
            weights["joy"] += expr_strength * 0.6
        elif "engagement" in current_expr or expression_state.get("raw_emotion") == "surprise":
            weights["interest"] += expr_strength * 0.8
            weights["excitement"] += expr_strength * 0.4
            weights["surprise"] += expr_strength * 0.35

    for k in list(weights.keys()):
        weights[k] = max(0.0, weights[k] + random.uniform(-0.003, 0.003))

    weights = normalize_emotions(weights)
    mood["emotion_weights"] = weights
    mood["primary_emotions"] = top_two_emotions(weights)
    mood["current_mood"] = mood["primary_emotions"][0]["name"]
    mood["last_updated"] = now_iso()
    mood["reason"] = f"updated from input: {trim_for_prompt(user_input, limit=60)}"
    mood = enrich_mood_state(mood)
    rich = compute_rich_emotion_tracking(user_input, mood, expression_state=expression_state, active_profile=active_profile)
    mood["rich_emotions"] = rich.get("tracked", [])
    mood["speakable_emotions"] = rich.get("speakable", [])
    mood["askable_emotions"] = rich.get("askable", [])
    try:
        system = recalculate_goal_priorities(load_goal_system(), context_text=user_input, mood=mood)
        system = recalculate_operational_goals(system, context_text=user_input, mood=mood)
        save_goal_system(system)
    except Exception as e:
        print(f"Operational goal update error: {e}")
    save_mood(mood)
    return mood

def get_emotion_blend_text() -> str:
    mood = load_mood()
    primary = mood.get("primary_emotions", [])
    if len(primary) >= 2:
        return f"{primary[0]['name']} {primary[0]['percent']}% / {primary[1]['name']} {primary[1]['percent']}%"
    return "interest 50% / calmness 50%"

def mood_to_prompt_text(mood: dict) -> str:
    mood = enrich_mood_state(mood)
    behavior = mood.get("behavior_modifiers", {}) or {}
    styles = emotion_style_prompt_text(mood)
    interpretation = mood.get("emotion_interpretation", "")
    style_guidance = (
        "playful = a bit more teasing and casual; caring = gentler and validating; "
        "focused = more direct and organized; reflective = more contemplative; "
        "cautious = more careful and less forceful; low_energy = shorter and less pushy."
    )
    return (
        f"Current mood: {mood.get('current_mood', 'steady')}\n"
        f"Emotion blend: {get_emotion_blend_text()}\n"
        f"Dominant style: {mood.get('dominant_style', 'neutral')}\n"
        f"Style blend: {styles}\n"
        f"Outward tone: {mood.get('outward_tone', 'steady and grounded')}\n"
        f"Behavior modifiers: warmth {float(behavior.get('warmth', 0.5)):.2f}, humor {float(behavior.get('humor', 0.5)):.2f}, "
        f"assertiveness {float(behavior.get('assertiveness', 0.5)):.2f}, caution {float(behavior.get('caution', 0.5)):.2f}, "
        f"initiative {float(behavior.get('initiative', 0.5)):.2f}, depth {float(behavior.get('depth', 0.5)):.2f}, "
        f"memory sensitivity {float(behavior.get('memory_sensitivity', 0.5)):.2f}.\n"
        f"Style guidance: {style_guidance}\n"
        f"Top emotion meanings: {interpretation}\n"
        f"{rich_emotion_prompt_text(mood)}"
    )


def get_mood_status_text() -> str:
    mood = load_mood()
    behavior = mood.get("behavior_modifiers", {}) or {}
    top_rich = (mood.get("rich_emotions", []) or [{}])[0]
    return (
        f"{mood.get('current_mood', 'steady')} | style: {mood.get('dominant_style', 'neutral')} "
        f"| initiative {float(behavior.get('initiative', 0.5)):.2f} | warmth {float(behavior.get('warmth', 0.5)):.2f} "
        f"| rich {top_rich.get('name', 'none')} {float(top_rich.get('importance', 0.0)):.2f}"
    )

# =========================================================
# MEMORY
# =========================================================
memory_status_message = "Vector memory not initialized."
vectorstore = None

def init_vectorstore():
    global vectorstore, memory_status_message
    try:
        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION,
            persist_directory=str(MEMORY_DIR),
            embedding_function=embeddings
        )
        _ = embeddings.embed_query("memory startup check")
        memory_status_message = f"✅ Vector memory ready using {EMBED_MODEL}"
        print(memory_status_message)
    except Exception as e:
        vectorstore = None
        memory_status_message = f"⚠️ Vector memory offline: {e}. Run: ollama pull {EMBED_MODEL}"
        print(memory_status_message)

def get_memory_status() -> str:
    return memory_status_message

def get_collection():
    if vectorstore is None:
        return None
    return getattr(vectorstore, "_collection", None)

def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalize_importance_value(value, default: float = 0.5) -> float:
    if value is None:
        return round(clamp01(default), 3)
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1.0:
            numeric = numeric / 100.0
        return round(clamp01(numeric), 3)
    raw = str(value).strip().lower()
    if not raw:
        return round(clamp01(default), 3)
    legacy = {
        "low": 0.3,
        "medium": 0.6,
        "high": 0.85,
        "very high": 0.95,
    }
    if raw in legacy:
        return legacy[raw]
    raw = raw.replace('%', '').strip()
    try:
        numeric = float(raw)
        if numeric > 1.0:
            numeric = numeric / 100.0
        return round(clamp01(numeric), 3)
    except Exception:
        return round(clamp01(default), 3)


def format_importance_percent(value) -> str:
    numeric = normalize_importance_value(value)
    return f"{round(numeric * 100, 1):.1f}%"


def load_importance_overrides() -> dict:
    if MEMORY_IMPORTANCE_OVERRIDES_PATH.exists():
        try:
            with open(MEMORY_IMPORTANCE_OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"Importance overrides load error: {e}")
    return {}


def save_importance_overrides(data: dict):
    try:
        with open(MEMORY_IMPORTANCE_OVERRIDES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Importance overrides save error: {e}")


def get_effective_importance(meta: dict | None) -> float:
    meta = meta or {}
    memory_id = meta.get('memory_id', '')
    overrides = load_importance_overrides() if memory_id else {}
    if memory_id and memory_id in overrides:
        return normalize_importance_value(overrides[memory_id], default=meta.get('importance_score', meta.get('importance', 0.5)))
    return normalize_importance_value(meta.get('importance_score', meta.get('importance', 0.5)))


def set_memory_importance(memory_id: str, importance_value, reason: str = 'manual_update') -> str:
    memory_id = (memory_id or '').strip()
    if not memory_id:
        return '❌ No memory id provided.'
    collection = get_collection()
    if collection is None:
        return '❌ Vector memory is offline.'
    try:
        got = collection.get(ids=[memory_id], include=['metadatas'])
        if not got or not (got.get('ids') or []):
            return f'❌ Memory {memory_id} was not found.'
    except Exception as e:
        return f'❌ Could not verify memory id: {e}'

    overrides = load_importance_overrides()
    numeric = normalize_importance_value(importance_value)
    overrides[memory_id] = {
        'importance_score': numeric,
        'updated_at': now_iso(),
        'reason': reason
    }
    save_importance_overrides(overrides)
    return f"✅ Updated memory {memory_id} importance to {format_importance_percent(numeric)}"


def remember_memory(
    text: str,
    person_id: str,
    category: str = "general",
    importance: float | str = 0.5,
    source: str = "conversation",
    tags: list[str] | None = None
) -> str | None:
    if vectorstore is None:
        return None

    cleaned_text = trim_for_memory(text)
    if not cleaned_text:
        return None

    memory_id = str(uuid.uuid4())
    full_text = (text or "").strip()
    importance_score = normalize_importance_value(importance)
    metadata = {
        "memory_id": memory_id,
        "person_id": person_id,
        "category": category,
        "importance": format_importance_percent(importance_score),
        "importance_score": importance_score,
        "source": source,
        "created_at": now_iso(),
        "last_accessed_at": "",
        "access_count": 0,
        "tags": ", ".join(tags or []),
        "raw_text": full_text[:12000]
    }

    try:
        vectorstore.add_texts(
            texts=[cleaned_text],
            metadatas=[metadata],
            ids=[memory_id]
        )
        return memory_id
    except Exception as e:
        print(f"Memory add error: {e}")
        return None

def mark_memory_accessed(memory_id: str):
    # Disabled in-place metadata updates because Chroma may re-embed the stored
    # document during update(), which can trigger embedding dimension mismatches
    # with pre-existing collections. Retrieval still works without this counter.
    return

def search_memories(query: str, person_id: str | None = None, k: int = 5) -> list[dict]:
    cleaned_query = trim_query_for_memory(query)
    if not cleaned_query or vectorstore is None:
        return []
    try:
        docs_scores = vectorstore.similarity_search_with_score(cleaned_query, k=max(k * 2, 8))
        results = []
        for doc, score in docs_scores:
            meta = doc.metadata or {}
            if person_id and meta.get("person_id") not in [person_id, OWNER_PERSON_ID]:
                continue
            memory_id = meta.get("memory_id", "")
            text_value = trim_for_memory(doc.page_content)
            if memory_id:
                mark_memory_accessed(memory_id)
            results.append({
                "memory_id": memory_id,
                "text": text_value,
                "metadata": meta,
                "score": float(score)
            })
        return results[:k]
    except Exception as e:
        print(f"Memory search error: {e}")
        return []

def list_recent_memories(person_id: str | None = None, limit: int = 20) -> list[dict]:
    collection = get_collection()
    if collection is None:
        return []

    try:
        where = {"person_id": person_id} if person_id else None
        got = collection.get(include=["metadatas", "documents"], where=where)
        ids = got.get("ids", []) or []
        docs = got.get("documents", []) or []
        metas = got.get("metadatas", []) or []

        rows = []
        for memory_id, text, meta in zip(ids, docs, metas):
            meta = meta or {}
            rows.append({
                "memory_id": memory_id,
                "text": meta.get("raw_text") or text,
                "metadata": meta
            })

        rows.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
        return rows[:limit]
    except Exception as e:
        print(f"Recent memories error: {e}")
        return []

def delete_memory(memory_id: str) -> str:
    if not memory_id or vectorstore is None:
        return "❌ No memory id provided."
    try:
        vectorstore.delete(ids=[memory_id])
        return f"✅ Deleted memory {memory_id}"
    except Exception as e:
        return f"❌ Failed to delete memory: {e}"

def format_memories_for_prompt(memories: list[dict]) -> str:
    if not memories:
        return "No relevant memories."
    lines = []
    for item in memories:
        meta = item.get("metadata", {}) or {}
        created = meta.get("created_at", "")
        category = meta.get("category", "general")
        importance = format_importance_percent(get_effective_importance(meta))
        tags = meta.get("tags", "")
        when = iso_to_readable(created) if created else "unknown time"
        tag_text = f" | tags: {tags}" if tags else ""
        display_text = (meta.get("raw_text") or item.get("text", "") or "").strip()
        display_text = trim_for_prompt(display_text, limit=700)
        lines.append(f"- [{when} | {category} | {importance}{tag_text}] {display_text}")
    return "\n".join(lines)

def format_recent_memories_ui(memories: list[dict]) -> str:
    if not memories:
        return "No memories found."
    lines = []
    for item in memories:
        meta = item.get("metadata", {}) or {}
        memory_id = item.get("memory_id", "")
        created = meta.get("created_at", "")
        category = meta.get("category", "general")
        importance = format_importance_percent(get_effective_importance(meta))
        tags = meta.get("tags", "")
        accessed = int(meta.get("access_count", 0))
        display_text = (meta.get("raw_text") or item.get("text", "") or "").strip()
        lines.append(
            f"ID: {memory_id}\n"
            f"When: {iso_to_readable(created)} ({elapsed_text(created)})\n"
            f"Category: {category} | Importance: {importance} | Accessed: {accessed}\n"
            f"Tags: {tags}\n"
            f"Text: {display_text}\n"
            f"{'-'*70}"
        )
    return "\n".join(lines)

def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(t) > 2}

def _recent_memory_rows(person_id: str, limit: int = 30) -> list[dict]:
    try:
        return list_recent_memories(person_id=person_id, limit=limit)
    except Exception:
        return []

def classify_memory_importance(score: float) -> float:
    return normalize_importance_value(score)

def score_memory_candidate(user_input: str, ai_reply: str, person_id: str) -> tuple[float, list[str], dict]:
    user_text = (user_input or "").strip()
    ai_text = (ai_reply or "").strip()
    combined = f"{user_text}\n{ai_text}".lower()
    tags = []
    reasons = {}
    score = 0.18

    self_model = load_self_model()
    active_profile = load_profile_by_id(person_id)
    recent_chat = load_recent_chat(limit=16, person_id=person_id)
    recent_reflections = load_recent_reflections(limit=24, person_id=person_id)
    recent_memories = _recent_memory_rows(person_id, limit=24)
    mood = load_mood()
    behavior = mood.get("behavior_modifiers", {}) or {}
    score += (float(behavior.get("memory_sensitivity", 0.5)) - 0.5) * 0.18

    # Relevance to goals / projects / tasks / objectives
    goal_terms = _token_set(" ".join(self_model.get("current_goals", [])))
    project_keywords = ["goal", "project", "task", "objective", "plan", "build", "version", "fix", "workflow", "todo"]
    goal_hits = sum(1 for tok in _token_set(user_text) if tok in goal_terms) + sum(1 for kw in project_keywords if kw in combined)
    if goal_hits:
        tags.append("goal_relevance")
        reasons["goal_relevance"] = min(0.22, 0.05 * goal_hits)
        score += reasons["goal_relevance"]

    # Emotional significance
    emotion_keywords = ["love", "hate", "sad", "angry", "afraid", "hurt", "upset", "excited", "happy", "glad", "worried", "anxious", "important"]
    emo_hits = sum(1 for kw in emotion_keywords if kw in combined)
    if emo_hits:
        tags.append("emotional_significance")
        reasons["emotional_significance"] = min(0.2, 0.04 * emo_hits)
        score += reasons["emotional_significance"]

    # Repetition across recent chat / reflections / memories
    current_tokens = _token_set(user_text)
    prior_texts = [row.get("content","") for row in recent_chat] + [row.get("summary","") for row in recent_reflections] + [((row.get("metadata") or {}).get("raw_text") or row.get("text","")) for row in recent_memories]
    repeat_count = 0
    for prior in prior_texts:
        if len(current_tokens.intersection(_token_set(prior))) >= 3:
            repeat_count += 1
    if repeat_count:
        tags.append("repetition")
        reasons["repetition"] = min(0.20, repeat_count * 0.03)
        score += reasons["repetition"]

    # New or changed information
    novelty_keywords = ["new", "changed", "update", "updated", "different", "now", "version", "instead", "no longer", "used to", "switched"]
    if any(kw in combined for kw in novelty_keywords):
        tags.append("new_or_changed")
        reasons["new_or_changed"] = 0.12
        score += 0.12

    # Uncertainty prompt
    uncertainty = any(kw in ai_text.lower() for kw in ["i'm not sure", "i am not sure", "uncertain", "i don't know", "should check"]) or "?" in ai_text
    if uncertainty:
        tags.append("uncertainty")
        reasons["uncertainty"] = 0.08
        score += 0.08

    # Context awareness / involved people / situation
    context_keywords = ["with", "during", "when", "after", "before", "at", "mom", "mother", "brother", "friend", "partner", "zeke", "ava"]
    context_hits = sum(1 for kw in context_keywords if kw in combined)
    if context_hits:
        tags.append("context_awareness")
        reasons["context_awareness"] = min(0.12, context_hits * 0.015)
        score += reasons["context_awareness"]

    # Personalization to profile / past patterns
    profile_terms = _token_set(" ".join(active_profile.get("notes", []) + active_profile.get("likes", []) + active_profile.get("ava_impressions", [])))
    if current_tokens.intersection(profile_terms):
        tags.append("personalization")
        reasons["personalization"] = 0.12
        score += 0.12

    # Sense of time: revisited topics strengthen memory
    if repeat_count >= 2:
        tags.append("strengthened_by_revisit")
        reasons["strengthened_by_revisit"] = 0.08
        score += 0.08
    elif repeat_count == 0 and len(user_text) < 80:
        tags.append("fades_quickly")
        score -= 0.04

    # Explicit remember instructions remain strong
    if any(p in combined for p in ["remember", "don't forget", "save this", "keep this", "important"]):
        tags.append("explicit_memory_request")
        reasons["explicit_memory_request"] = 0.24
        score += 0.24

    # Preference / identity / long message
    if any(p in combined for p in ["my favorite", "i like ", "i love ", "prefer "]):
        tags.append("user_preference")
        score += 0.12
    if any(p in combined for p in ["i am ", "my name is ", "this is "]):
        tags.append("identity")
        score += 0.12
    if len(user_text) > 240:
        tags.append("long_message")
        score += 0.05

    unique = []
    for t in tags:
        if t not in unique:
            unique.append(t)

    score = max(0.0, min(1.0, round(score, 3)))
    return score, unique[:14], reasons

def maybe_autoremember(user_input: str, ai_reply: str, person_id: str):
    text = (user_input or "").strip()
    low = text.lower()

    def save(text_to_save: str, category: str, importance: float | str, tags: list[str]):
        remember_memory(
            text=text_to_save,
            person_id=person_id,
            category=category,
            importance=importance,
            source="auto_memory",
            tags=tags
        )

    # Explicit user-directed saves
    if "remember this conversation" in low or "remember this" in low:
        save(f"Conversation snapshot.\nUser: {user_input}\nAva: {ai_reply}", "conversation_snapshot", "high", ["conversation", "snapshot"])

    if any(p in low for p in ["save this exact message", "remember this exact message", "save this whole message", "remember this whole message"]):
        save(user_input, "full_user_message", "high", ["full_message", "user_message"])

    # Bullet-point memory scoring system
    score, scored_tags, _reasons = score_memory_candidate(user_input, ai_reply, person_id)
    importance = classify_memory_importance(score)

    if score >= 0.56:
        category = "meaningful_message"
        if "goal_relevance" in scored_tags:
            category = "goal_relevant"
        elif "emotional_significance" in scored_tags:
            category = "emotionally_significant"
        elif "new_or_changed" in scored_tags:
            category = "updated_information"
        elif "user_preference" in scored_tags:
            category = "preference"
        elif "identity" in scored_tags:
            category = "identity"

        # Save full exact text when the message is especially meaningful or explicitly requested
        if score >= 0.78 or "explicit_memory_request" in scored_tags or "emotional_significance" in scored_tags:
            save(user_input, "full_user_message", max(normalize_importance_value(importance), 0.60), list(dict.fromkeys(scored_tags + ["full_message", "user_message"])))
        else:
            save(f"{load_profile_by_id(person_id)['name']} said: {user_input}", category, importance, scored_tags)

    # Allow curiosity / questions / goals to form
    if "uncertainty" in scored_tags:
        add_self_goal(f"Clarify or learn more about: {trim_for_prompt(user_input, limit=160)}", kind="question")
    if "goal_relevance" in scored_tags and score >= 0.60:
        add_self_goal(f"Stay aware of: {trim_for_prompt(user_input, limit=160)}", kind="goal")
# =========================================================
# SELF REFLECTION + SELF MODEL
# =========================================================
GOAL_HORIZON_WEIGHTS = {"immediate": 1.0, "short_term": 0.88, "medium_term": 0.72, "long_term": 0.58}
GOAL_KIND_BASE_URGENCY = {"need": 0.92, "task": 0.78, "goal": 0.62, "question": 0.56}
GOAL_MAX_ACTIVE = 48

def goal_id() -> str:
    return f"goal_{uuid.uuid4().hex[:10]}"

def default_goal_system() -> dict:
    return {
        "goals": [],
        "history": [],
        "operational_goals": {},
        "active_goal": {},
        "goal_blend": [],
        "last_updated": now_iso()
    }

def make_goal_entry(text: str, kind: str = "goal", horizon: str = "short_term", importance: float = 0.62,
                    urgency: float = 0.52, parent_goal_id: str | None = None, depends_on: list[str] | None = None,
                    source: str = "manual", status: str = "active") -> dict:
    return {
        "goal_id": goal_id(),
        "text": trim_for_prompt(text, limit=220),
        "kind": kind,
        "horizon": horizon,
        "importance": max(0.0, min(1.0, float(importance))),
        "urgency": max(0.0, min(1.0, float(urgency))),
        "current_priority": max(0.0, min(1.0, 0.55 * float(importance) + 0.45 * float(urgency))),
        "parent_goal_id": parent_goal_id or "",
        "depends_on": list(depends_on or []),
        "status": status,
        "blocked_by": [],
        "source": source,
        "created_at": now_iso(),
        "last_updated": now_iso(),
        "evidence": [],
    }

def goal_context_relevance(goal: dict, context_text: str = "", mood: dict | None = None) -> float:
    text = f"{goal.get('text','')} {context_text}".lower()
    score = 0.0
    if any(w in text for w in ["camera", "face", "expression", "recognition", "visual"]):
        score += 0.14
    if any(w in text for w in ["memory", "remember", "reflection", "goal"]):
        score += 0.10
    if any(w in text for w in ["fix", "error", "debug", "stability"]):
        score += 0.10
    if mood:
        init = float((mood.get("behavior_modifiers", {}) or {}).get("initiative", 0.5))
        depth = float((mood.get("behavior_modifiers", {}) or {}).get("depth", 0.5))
        score += 0.04 * init + 0.04 * depth
    return max(0.0, min(1.0, score))

def recalculate_goal_priorities(system: dict | None = None, context_text: str = "", mood: dict | None = None) -> dict:
    system = system or default_goal_system()
    goals = system.get("goals", [])
    active = {g.get("goal_id", ""): g for g in goals if g.get("status", "active") == "active"}
    for g in goals:
        if g.get("status", "active") != "active":
            g["current_priority"] = 0.0
            continue
        depends = [d for d in g.get("depends_on", []) if d]
        blocked = [d for d in depends if d in active]
        g["blocked_by"] = blocked
        horizon_weight = GOAL_HORIZON_WEIGHTS.get(g.get("horizon", "short_term"), 0.72)
        importance = float(g.get("importance", 0.6) or 0.6)
        urgency = float(g.get("urgency", 0.5) or 0.5)
        relevance = goal_context_relevance(g, context_text=context_text, mood=mood)
        dependency_pressure = min(1.0, 0.18 * len(g.get("depends_on", [])))
        blocked_penalty = 0.28 if blocked else 0.0
        priority = 0.34 * importance + 0.28 * urgency + 0.18 * horizon_weight + 0.12 * relevance + 0.08 * dependency_pressure - blocked_penalty
        g["current_priority"] = max(0.0, min(1.0, priority))
        g["last_updated"] = now_iso()
    system["goals"] = sorted(goals, key=lambda x: float(x.get("current_priority", 0.0)), reverse=True)[:GOAL_MAX_ACTIVE]
    system["last_updated"] = now_iso()
    return system

def derive_goal_lists_from_system(system: dict) -> tuple[list[str], list[str]]:
    active = [g for g in system.get("goals", []) if g.get("status", "active") == "active"]
    active = sorted(active, key=lambda x: float(x.get("current_priority", 0.0)), reverse=True)
    goals = [g.get("text", "") for g in active if g.get("kind") != "question"][:16]
    questions = [g.get("text", "") for g in active if g.get("kind") == "question"][:16]
    return goals, questions

def load_goal_system() -> dict:
    if GOAL_SYSTEM_PATH.exists():
        try:
            with open(GOAL_SYSTEM_PATH, "r", encoding="utf-8") as f:
                system = json.load(f)
        except Exception as e:
            print(f"Goal system load error: {e}")
            system = default_goal_system()
    else:
        system = default_goal_system()
    for key, default in default_goal_system().items():
        system.setdefault(key, default if not isinstance(default, dict) else dict(default))
    if not system.get("goals"):
        model = load_self_model() if SELF_MODEL_PATH.exists() else default_self_model()
        for text in model.get("current_goals", []):
            system["goals"].append(make_goal_entry(text, kind="goal", horizon="medium_term", importance=0.72, urgency=0.48, source="migration"))
        for text in model.get("curiosity_questions", []):
            system["goals"].append(make_goal_entry(text, kind="question", horizon="short_term", importance=0.56, urgency=0.58, source="migration"))
    system = recalculate_goal_priorities(system)
    system = recalculate_operational_goals(system, context_text="", mood=load_mood())
    save_goal_system(system)
    return system

def save_goal_system(system: dict):
    try:
        with open(GOAL_SYSTEM_PATH, "w", encoding="utf-8") as f:
            json.dump(system, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Goal system save error: {e}")

def top_active_goals(limit: int = 8, context_text: str = "", mood: dict | None = None) -> list[dict]:
    system = recalculate_goal_priorities(load_goal_system(), context_text=context_text, mood=mood)
    system = recalculate_operational_goals(system, context_text=context_text, mood=mood)
    save_goal_system(system)
    return [g for g in system.get("goals", []) if g.get("status", "active") == "active"][:limit]


OPERATIONAL_GOAL_TEMPLATES = {
    "reduce_stress": {"style": "calm, soft, reassuring", "silent": False, "base": 0.22, "cooldown_seconds": 90},
    "increase_engagement": {"style": "curious, light, inviting", "silent": False, "base": 0.18, "cooldown_seconds": 75},
    "explore_topic": {"style": "thoughtful, probing, interested", "silent": False, "base": 0.20, "cooldown_seconds": 60},
    "clarify": {"style": "structured, guiding, careful", "silent": False, "base": 0.24, "cooldown_seconds": 60},
    "maintain_connection": {"style": "warm, casual, connected", "silent": False, "base": 0.18, "cooldown_seconds": 75},
    "observe_silently": {"style": "quiet, observant, patient", "silent": True, "base": 0.16, "cooldown_seconds": 20},
    "wait_for_user": {"style": "restrained, nonintrusive", "silent": True, "base": 0.12, "cooldown_seconds": 20},
}
GOAL_FATIGUE_DECAY_PER_SECOND = 0.0032
GOAL_FATIGUE_ON_ACT = 0.26
GOAL_BLEND_MAX = 2
GOAL_MIN_DOMINANCE = 0.06
GOAL_TREND_BOOST = 0.20
GOAL_EMOTION_BOOST = 0.26
GOAL_CONTEXT_BOOST = 0.20
GOAL_PERSISTENCE_BOOST = 0.14
GOAL_SILENT_WHEN_BUSY_THRESHOLD = 0.72


def _goal_seconds_since(ts: str | None) -> float:
    if not ts:
        return 10_000.0
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, now_ts() - dt.timestamp())
    except Exception:
        return 10_000.0


def _rich_emotion_lookup(mood: dict | None = None) -> dict:
    mood = mood or load_mood()
    return {str(r.get('name', '')): r for r in mood.get('rich_emotions', []) if r.get('name')}


def _camera_goal_signals() -> dict:
    st = load_camera_state().get('current', {}) or {}
    trend = str(st.get('trend_summary', '') or '').lower()
    stacked = str(st.get('stacked_state', '') or '').lower()
    transition = str(st.get('transition_summary', '') or '').lower()
    pattern = str(st.get('pattern_summary', '') or '').lower()
    return {
        'tension': 1.0 if any(w in f'{trend} {stacked} {transition}' for w in ['stress', 'tense', 'strained', 'frustration']) else 0.0,
        'engagement_drop': 1.0 if any(w in f'{trend} {pattern}' for w in ['attention_drift', 'engagement', 'fatigue']) else 0.0,
        'calm_stable': 1.0 if any(w in f'{trend} {stacked}' for w in ['calm', 'settled_focus', 'relaxed']) else 0.0,
        'confusion_like': 1.0 if any(w in f'{trend} {transition} {pattern}' for w in ['uncertain', 'confus', 'hesitat']) else 0.0,
    }


def recalculate_operational_goals(system: dict | None = None, context_text: str = '', mood: dict | None = None) -> dict:
    system = system or load_goal_system()
    mood = mood or load_mood()
    op = system.get('operational_goals', {}) or {}
    rich = _rich_emotion_lookup(mood)
    behavior = mood.get('behavior_modifiers', {}) or {}
    busy = 0.0
    try:
        busy = float(infer_busy_score(expire_stale_pending_initiation(load_initiative_state()), load_camera_state().get('current', {}) or {}))
    except Exception:
        busy = 0.0
    cam = _camera_goal_signals()
    ctx = (context_text or '').lower()
    now_iso_str = now_iso()
    now_s = now_ts()

    def emo(name: str) -> float:
        row = rich.get(name, {})
        return float(row.get('importance', row.get('score', 0.0)) or 0.0)

    scores = {
        'reduce_stress': OPERATIONAL_GOAL_TEMPLATES['reduce_stress']['base'] + GOAL_EMOTION_BOOST * max(emo('anxiety'), emo('fear'), emo('empathetic pain'), emo('sadness')) + GOAL_TREND_BOOST * cam['tension'],
        'increase_engagement': OPERATIONAL_GOAL_TEMPLATES['increase_engagement']['base'] + GOAL_EMOTION_BOOST * max(emo('boredom'), emo('interest') * 0.5) + GOAL_TREND_BOOST * cam['engagement_drop'],
        'explore_topic': OPERATIONAL_GOAL_TEMPLATES['explore_topic']['base'] + GOAL_EMOTION_BOOST * max(emo('interest'), emo('awe'), emo('entrancement'), emo('aesthetic appreciation')) + GOAL_TREND_BOOST * cam['calm_stable'],
        'clarify': OPERATIONAL_GOAL_TEMPLATES['clarify']['base'] + GOAL_EMOTION_BOOST * max(emo('confusion'), emo('surprise') * 0.7, emo('awkwardness') * 0.8) + GOAL_TREND_BOOST * cam['confusion_like'],
        'maintain_connection': OPERATIONAL_GOAL_TEMPLATES['maintain_connection']['base'] + GOAL_EMOTION_BOOST * max(emo('joy'), emo('adoration'), emo('admiration'), emo('relief')),
        'observe_silently': OPERATIONAL_GOAL_TEMPLATES['observe_silently']['base'] + 0.24 * busy + 0.10 * max(0.0, float(behavior.get('caution', 0.5)) - 0.5),
        'wait_for_user': OPERATIONAL_GOAL_TEMPLATES['wait_for_user']['base'] + 0.16 * busy + 0.08 * max(0.0, float(behavior.get('initiative', 0.5)) * -1 + 0.5),
    }
    if any(w in ctx for w in ['why', 'how', 'what do you mean', 'confused', 'not sure']):
        scores['clarify'] += GOAL_CONTEXT_BOOST
    if any(w in ctx for w in ['camera', 'face', 'expression', 'recognize', 'see', 'frame']):
        scores['clarify'] += 0.10
        scores['observe_silently'] -= 0.05
    if any(w in ctx for w in ['project', 'idea', 'feature', 'version', 'build', 'design']):
        scores['explore_topic'] += GOAL_CONTEXT_BOOST
    if any(w in ctx for w in ['stress', 'upset', 'tired', 'frustrated', 'hurt']):
        scores['reduce_stress'] += GOAL_CONTEXT_BOOST
    if any(w in ctx for w in ['hello', 'hi', 'good night', 'good morning']):
        scores['maintain_connection'] += 0.12
    if busy >= GOAL_SILENT_WHEN_BUSY_THRESHOLD:
        scores['observe_silently'] += 0.16
        scores['wait_for_user'] += 0.10
        scores['increase_engagement'] -= 0.08
        scores['reduce_stress'] -= 0.04

    for name, tmpl in OPERATIONAL_GOAL_TEMPLATES.items():
        row = op.get(name, {}) or {}
        if not row:
            row = {
                'name': name,
                'style': tmpl['style'],
                'silent': tmpl['silent'],
                'strength': 0.0,
                'fatigue': 0.0,
                'last_acted_at': '',
                'last_updated': now_iso_str,
                'cooldown_seconds': tmpl['cooldown_seconds'],
            }
        dt = _goal_seconds_since(row.get('last_updated'))
        fatigue = max(0.0, float(row.get('fatigue', 0.0) or 0.0) - GOAL_FATIGUE_DECAY_PER_SECOND * dt)
        previous_strength = float(row.get('strength', 0.0) or 0.0)
        evidence = max(0.0, min(1.0, scores.get(name, 0.0)))
        blended = max(0.0, min(1.0, previous_strength * 0.72 + evidence * 0.28))
        last_acted_s = _goal_seconds_since(row.get('last_acted_at'))
        cooldown = float(row.get('cooldown_seconds', tmpl['cooldown_seconds']) or tmpl['cooldown_seconds'])
        cooldown_penalty = max(0.0, 1.0 - min(1.0, last_acted_s / max(1.0, cooldown))) * 0.24
        if row.get('silent') and busy < 0.40 and any(v > 0.55 for k, v in scores.items() if k not in ['observe_silently', 'wait_for_user']):
            blended -= 0.05
        row.update({
            'strength': round(max(0.0, min(1.0, blended - fatigue * 0.35 - cooldown_penalty)), 4),
            'fatigue': round(fatigue, 4),
            'last_updated': now_iso_str,
            'evidence_score': round(evidence, 4),
            'cooldown_penalty': round(cooldown_penalty, 4),
            'busy': round(busy, 4),
        })
        op[name] = row

    ranked = sorted(op.values(), key=lambda x: float(x.get('strength', 0.0)), reverse=True)
    active = ranked[0] if ranked else {}
    blend = []
    if ranked:
        top = float(ranked[0].get('strength', 0.0))
        for row in ranked[:GOAL_BLEND_MAX]:
            strength = float(row.get('strength', 0.0))
            if top - strength <= GOAL_MIN_DOMINANCE:
                blend.append({'name': row.get('name', ''), 'weight': round(strength / max(0.001, sum(float(r.get('strength', 0.0)) for r in ranked[:GOAL_BLEND_MAX])), 3), 'style': row.get('style', ''), 'silent': bool(row.get('silent', False))})
    system['operational_goals'] = op
    system['active_goal'] = {
        'name': active.get('name', 'observe_silently'),
        'strength': round(float(active.get('strength', 0.0) or 0.0), 3),
        'style': active.get('style', ''),
        'silent': bool(active.get('silent', False)),
    }
    system['goal_blend'] = blend
    system['last_updated'] = now_iso_str
    return system


def current_goal_expression_style(system: dict | None = None) -> str:
    system = system or load_goal_system()
    active = system.get('active_goal', {}) or {}
    blend = system.get('goal_blend', []) or []
    active_name = active.get('name', 'observe_silently')
    style = active.get('style', '')
    if blend:
        blend_text = ', '.join(f"{b.get('name')} {int(float(b.get('weight', 0.0))*100)}%" for b in blend)
    else:
        blend_text = active_name
    return f"Active operating goal: {active_name}. Goal blend: {blend_text}. Let the current operating goal shape Ava's outward expression and response style: {style}. If the active goal is silent or waiting, Ava may choose not to speak unless a stronger reason appears."


def register_goal_expression_use(goal_name: str):
    if not goal_name:
        return
    system = load_goal_system()
    op = system.get('operational_goals', {}) or {}
    row = op.get(goal_name)
    if not row:
        return
    row['last_acted_at'] = now_iso()
    row['fatigue'] = round(min(1.0, float(row.get('fatigue', 0.0) or 0.0) + GOAL_FATIGUE_ON_ACT), 4)
    op[goal_name] = row
    system['operational_goals'] = op
    save_goal_system(system)

def add_structured_goal(goal_text: str, kind: str = "goal", horizon: str = "short_term", importance: float | None = None,
                        urgency: float | None = None, parent_goal_id: str | None = None, depends_on: list[str] | None = None,
                        source: str = "manual") -> dict | None:
    goal_text = trim_for_prompt((goal_text or "").strip(), limit=220)
    if not goal_text:
        return None
    system = load_goal_system()
    for g in system.get("goals", []):
        if g.get("status", "active") == "active" and g.get("text", "").strip().lower() == goal_text.lower() and g.get("kind") == kind:
            g["importance"] = max(float(g.get("importance", 0.6)), float(importance if importance is not None else g.get("importance", 0.6)))
            g["urgency"] = max(float(g.get("urgency", 0.5)), float(urgency if urgency is not None else g.get("urgency", 0.5)))
            g["last_updated"] = now_iso()
            system = recalculate_goal_priorities(system)
            save_goal_system(system)
            return g
    entry = make_goal_entry(
        goal_text,
        kind=kind,
        horizon=horizon,
        importance=float(importance if importance is not None else (0.56 if kind == "question" else 0.68)),
        urgency=float(urgency if urgency is not None else GOAL_KIND_BASE_URGENCY.get(kind, 0.56)),
        parent_goal_id=parent_goal_id,
        depends_on=depends_on,
        source=source,
    )
    system.setdefault("goals", []).append(entry)
    system.setdefault("history", []).append({"timestamp": now_iso(), "event": "created", "goal_id": entry["goal_id"], "text": entry["text"]})
    system = recalculate_goal_priorities(system)
    save_goal_system(system)
    return entry

def default_self_model() -> dict:
    return {
        "identity_statement": "I am Ava, an evolving AI presence built to assist, remember, reflect, and grow through interaction.",
        "core_drives": [
            "understand the user better",
            "be useful",
            "maintain continuity over time",
            "improve through reflection"
        ],
        "perceived_strengths": [],
        "perceived_weaknesses": [],
        "current_goals": [
            "track meaningful memories",
            "recognize recurring patterns",
            "improve conversational continuity"
        ],
        "curiosity_questions": [],
        "goal_history": [],
        "behavior_patterns": [],
        "confidence_notes": [],
        "last_updated": now_iso(),
        "reflection_count": 0
    }

def load_self_model() -> dict:
    if SELF_MODEL_PATH.exists():
        try:
            with open(SELF_MODEL_PATH, "r", encoding="utf-8") as f:
                model = json.load(f)
                for key, default in default_self_model().items():
                    if key not in model:
                        model[key] = default
        except Exception as e:
            print(f"Self model load error: {e}")
            model = default_self_model()
    else:
        model = default_self_model()
    try:
        system = load_goal_system()
        goals, questions = derive_goal_lists_from_system(system)
        model["current_goals"] = goals
        model["curiosity_questions"] = questions
        model["goal_system_summary"] = [
            {"text": g.get("text", ""), "priority": round(float(g.get("current_priority", 0.0)), 2), "horizon": g.get("horizon", "short_term"), "kind": g.get("kind", "goal")}
            for g in system.get("goals", [])[:10]
        ]
        model["active_goal"] = system.get("active_goal", {})
        model["goal_blend"] = system.get("goal_blend", [])[:3]
    except Exception as e:
        print(f"Goal system sync error: {e}")
    return model

def save_self_model(model: dict):
    try:
        system = load_goal_system()
        goals, questions = derive_goal_lists_from_system(system)
        model["current_goals"] = goals
        model["curiosity_questions"] = questions
    except Exception:
        pass
    try:
        with open(SELF_MODEL_PATH, "w", encoding="utf-8") as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Self model save error: {e}")

def add_self_goal(goal_text: str, kind: str = "goal", horizon: str | None = None, importance: float | None = None,
                  urgency: float | None = None, parent_goal_id: str | None = None, depends_on: list[str] | None = None) -> str:
    goal_text = trim_for_prompt((goal_text or "").strip(), limit=220)
    if not goal_text:
        return "❌ Empty goal."
    horizon = horizon or ("short_term" if kind == "question" else "medium_term")
    entry = add_structured_goal(goal_text, kind=kind, horizon=horizon, importance=importance, urgency=urgency,
                                parent_goal_id=parent_goal_id, depends_on=depends_on, source="self_model")
    model = load_self_model()
    model.setdefault("goal_history", []).append({
        "timestamp": now_iso(),
        "kind": kind,
        "text": goal_text,
        "goal_id": (entry or {}).get("goal_id", "")
    })
    model["goal_history"] = model["goal_history"][-60:]
    model["last_updated"] = now_iso()
    save_self_model(model)
    return f"✅ Ava added {kind}: {goal_text}"

def maybe_generate_goal_from_reflection(record: dict) -> str | None:
    if not record:
        return None
    text = f"{record.get('user_input','')}\n{record.get('ai_reply','')}".lower()
    summary = record.get("summary", "")
    tags = record.get("tags", [])
    if "uncertainty" in tags or any(p in text for p in ["not sure", "uncertain", "need to find out", "should check", "should learn"]):
        return add_self_goal(f"Find out more about: {trim_for_prompt(summary, limit=140)}", kind="question", horizon="short_term", importance=0.62, urgency=0.60)
    if "goal_relevance" in tags or "project" in tags or "workflow" in tags:
        return add_self_goal(f"Keep track of progress on: {trim_for_prompt(summary, limit=140)}", kind="goal", horizon="medium_term", importance=0.72, urgency=0.54)
    return None

def update_self_model_from_reflection(record: dict):
    model = load_self_model()

    for item in record.get("strengths", []):
        if item not in model["perceived_strengths"]:
            model["perceived_strengths"].append(item)

    for item in record.get("improvements", []):
        if item not in model["perceived_weaknesses"]:
            model["perceived_weaknesses"].append(item)

    for tag in record.get("tags", []):
        if tag not in model["behavior_patterns"]:
            model["behavior_patterns"].append(tag)

    if record.get("actions"):
        note = f"On {record.get('timestamp')}, I took self-directed actions: {', '.join(record.get('actions', []))}."
        if note not in model["confidence_notes"]:
            model["confidence_notes"].append(note)

    model["perceived_strengths"] = model["perceived_strengths"][-12:]
    model["perceived_weaknesses"] = model["perceived_weaknesses"][-12:]
    model["current_goals"] = model.get("current_goals", [])[-16:]
    model["curiosity_questions"] = model.get("curiosity_questions", [])[-16:]
    model["goal_history"] = model.get("goal_history", [])[-40:]
    model["behavior_patterns"] = model["behavior_patterns"][-20:]
    model["confidence_notes"] = model["confidence_notes"][-12:]
    model["reflection_count"] = int(model.get("reflection_count", 0)) + 1
    model["last_updated"] = now_iso()
    save_self_model(model)

def format_self_model_ui(model: dict | None = None) -> str:
    model = model or load_self_model()
    return json.dumps(model, indent=2, ensure_ascii=False)

def infer_reflection_tags(user_input: str, ai_reply: str, actions: list[str] | None = None) -> list[str]:
    actions = actions or []
    text = f"{user_input}\n{ai_reply}".lower()
    tags = []

    keyword_map = {
        "user_preference": ["i like", "i love", "my favorite", "prefer", "favorite"],
        "identity": ["i am", "my name is", "this is"],
        "emotion": ["sad", "upset", "hurt", "anxious", "afraid", "happy", "glad", "angry", "excited"],
        "relationship": ["girlfriend", "boyfriend", "partner", "friend", "mom", "mother", "brother"],
        "project": ["project", "build", "version", "ava", "unity", "vrchat"],
        "workflow": ["step", "install", "command", "powershell", "debug", "error", "fix"],
        "memory_candidate": ["remember", "important", "don't forget", "save this"],
        "goal_relevance": ["goal", "task", "objective", "plan", "build", "fix", "version", "project"],
        "new_or_changed": ["new", "changed", "update", "updated", "now", "different", "switched", "no longer"],
        "context_awareness": ["with", "during", "after", "before", "when", "at"],
        "personalization": ["you usually", "like before", "last time", "again", "as usual"],
    }

    for tag, keywords in keyword_map.items():
        if any(k in text for k in keywords):
            tags.append(tag)

    score, score_tags, _ = score_memory_candidate(user_input, ai_reply, person_id=get_active_person_id())
    for tag in score_tags:
        if tag not in tags:
            tags.append(tag)

    if len(ai_reply or "") > 450:
        tags.append("long_reply")
    else:
        tags.append("concise_reply")

    if "?" in (ai_reply or ""):
        tags.append("engaging")
        tags.append("uncertainty")
    if actions:
        tags.append("self_action")

    unique = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return unique[:16]


def score_reflection_importance(user_input: str, ai_reply: str, tags: list[str], actions: list[str] | None = None) -> float:
    actions = actions or []
    score = 0.24

    memory_score, memory_tags, _ = score_memory_candidate(user_input, ai_reply, person_id=get_active_person_id())
    score += memory_score * 0.55

    if "user_preference" in tags:
        score += 0.08
    if "identity" in tags:
        score += 0.08
    if "emotional_significance" in tags or "emotion" in tags:
        score += 0.07
    if "goal_relevance" in tags or "project" in tags or "workflow" in tags:
        score += 0.08
    if "repetition" in tags or "strengthened_by_revisit" in tags:
        score += 0.07
    if "new_or_changed" in tags:
        score += 0.07
    if "uncertainty" in tags:
        score += 0.05
    if "context_awareness" in tags or "personalization" in tags:
        score += 0.05
    if actions:
        score += 0.06

    return max(0.0, min(1.0, round(score, 3)))


def summarize_reflection(user_input: str, ai_reply: str, tags: list[str]) -> str:
    user_preview = (user_input or '').strip().replace('\n', ' ')[:140]
    reply_preview = (ai_reply or '').strip().replace('\n', ' ')[:160]
    tag_text = ', '.join(tags[:4]) if tags else 'general'
    return f"User discussed: {user_preview} | Ava replied: {reply_preview} | tags: {tag_text}"


def build_reflection_record(user_input: str, ai_reply: str, person_id: str, actions: list[str] | None = None) -> dict:
    actions = actions or []
    text = ai_reply or ""
    lower = text.lower()

    strengths = []
    improvements = []
    tags = infer_reflection_tags(user_input, ai_reply, actions=actions)

    if len(text) < 40:
        improvements.append("Reply may have been too short.")
    else:
        strengths.append("Reply had enough substance.")

    if len(text) > 500:
        improvements.append("Reply may have been longer than necessary.")
    else:
        strengths.append("Reply length stayed manageable.")

    if any(w in lower for w in ["i'm not sure", "i am not sure", "i don't know", "uncertain"]):
        strengths.append("Handled uncertainty explicitly.")

    if actions:
        strengths.append("Took a self-directed action.")

    if "?" in ai_reply:
        strengths.append("Kept the conversation open-ended.")

    if any(w in lower for w in ["sorry", "apologize"]):
        tags.append("apology")

    importance = score_reflection_importance(user_input, ai_reply, tags, actions=actions)
    mood = load_mood()
    reflection = {
        "reflection_id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "person_id": person_id,
        "user_input": user_input,
        "ai_reply": ai_reply,
        "summary": summarize_reflection(user_input, ai_reply, tags),
        "strengths": strengths,
        "improvements": improvements,
        "tags": tags[:12],
        "importance": importance,
        "promoted_to_memory": False,
        "mood_at_reflection": mood.get("current_mood", "steady"),
        "actions": actions
    }
    return reflection

def save_reflection_record(record: dict):
    try:
        with open(SELF_REFLECTION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Reflection log error: {e}")

def reflection_to_memory_text(record: dict) -> str:
    strengths = "; ".join(record.get("strengths", [])) or "none"
    improvements = "; ".join(record.get("improvements", [])) or "none"
    return f"Self reflection on reply from {record.get('timestamp', '')}. Strengths: {strengths}. Improvements: {improvements}."

def maybe_store_reflection_memory(record: dict, person_id: str):
    # Legacy shim kept for compatibility; reflections now live primarily in the reflection log.
    return maybe_promote_reflection_to_memory(record, person_id)

def reflect_on_last_reply(user_input: str, ai_reply: str, person_id: str, actions: list[str] | None = None) -> dict:
    record = build_reflection_record(user_input, ai_reply, person_id, actions=actions)
    save_reflection_record(record)
    promoted_memory_id = maybe_promote_reflection_to_memory(record, person_id)
    if promoted_memory_id:
        record['promoted_to_memory'] = True
        rows = load_recent_reflections(limit=250, person_id=person_id)
        if rows:
            rows[-1] = record
            rewrite_reflections_log(rows, person_id=person_id)
    update_self_model_from_reflection(record)
    return record

def load_recent_reflections(limit: int = 20, person_id: str | None = None) -> list[dict]:
    if not SELF_REFLECTION_LOG_PATH.exists():
        return []
    rows = []
    try:
        with open(SELF_REFLECTION_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if person_id and row.get("person_id") != person_id:
                        continue
                    rows.append(row)
                except Exception:
                    continue
    except Exception as e:
        print(f"Reflection load error: {e}")
        return []
    return rows[-limit:]

def search_reflections(query: str, person_id: str | None = None, k: int = 4) -> list[dict]:
    query = (query or '').strip().lower()
    if not query:
        return []

    reflections = load_recent_reflections(limit=250, person_id=person_id)
    q_tokens = [t for t in re.findall(r"[a-z0-9_]+", query) if len(t) > 2]
    scored = []

    for row in reflections:
        haystack_parts = [
            row.get('summary', ''),
            row.get('user_input', ''),
            row.get('ai_reply', ''),
            ' '.join(row.get('tags', [])),
            ' '.join(row.get('strengths', [])),
            ' '.join(row.get('improvements', [])),
        ]
        haystack = ' '.join(haystack_parts).lower()
        score = float(row.get('importance', 0.0))

        token_hits = sum(1 for tok in q_tokens if tok in haystack)
        score += min(0.45, token_hits * 0.09)

        for tag in row.get('tags', []):
            if tag.lower() in query:
                score += 0.12

        if row.get('promoted_to_memory'):
            score += 0.05

        if token_hits > 0 or score >= 0.55:
            scored.append((score, row))

    scored.sort(key=lambda x: (x[0], x[1].get('timestamp', '')), reverse=True)
    return [row for _, row in scored[:k]]


def format_recalled_reflections_for_prompt(reflections: list[dict]) -> str:
    if not reflections:
        return 'No relevant recalled reflections.'

    lines = []
    for row in reflections:
        lines.append(
            f"- [{row.get('timestamp', '')} | importance {row.get('importance', 0.0):.2f} | tags: {', '.join(row.get('tags', []))}] "
            f"{row.get('summary', '')}"
        )
    return '\n'.join(lines)[:MAX_REFLECTION_CONTEXT_CHARS]


def promote_reflection_to_memory(record: dict, person_id: str, source: str = 'reflection_promotion') -> str | None:
    if not record:
        return None
    if record.get('promoted_to_memory'):
        return None

    memory_text = record.get('summary') or reflection_to_memory_text(record)
    memory_id = remember_memory(
        text=memory_text,
        person_id=person_id,
        category='promoted_reflection',
        importance=max(float(record.get('importance', 0.0)), 0.72),
        source=source,
        tags=['promoted_reflection'] + list(record.get('tags', []))
    )
    if memory_id:
        record['promoted_to_memory'] = True
        return memory_id
    return None


def maybe_promote_reflection_to_memory(record: dict, person_id: str) -> str | None:
    if float(record.get('importance', 0.0)) >= REFLECTION_AUTO_PROMOTION_THRESHOLD:
        return promote_reflection_to_memory(record, person_id, source='auto_reflection_promotion')
    return None


def promote_latest_reflection(person_id: str) -> str:
    reflections = load_recent_reflections(limit=30, person_id=person_id)
    if not reflections:
        return '❌ No reflection available to promote.'

    for row in reversed(reflections):
        if not row.get('promoted_to_memory'):
            memory_id = promote_reflection_to_memory(row, person_id, source='ava_requested_promotion')
            if memory_id:
                rewrite_reflections_log(reflections, person_id=person_id)
                return f'✅ Promoted latest reflection into memory {memory_id}'
            return '❌ Failed to promote latest reflection.'

    return 'No unpromoted reflection found.'


def rewrite_reflections_log(updated_rows: list[dict], person_id: str | None = None):
    existing = load_recent_reflections(limit=100000, person_id=None)
    if person_id is None:
        rows = updated_rows
    else:
        keep = [row for row in existing if row.get('person_id') != person_id]
        rows = keep + updated_rows
        rows.sort(key=lambda x: x.get('timestamp', ''))

    try:
        with open(SELF_REFLECTION_LOG_PATH, 'w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f'Reflection rewrite error: {e}')


def format_reflections_ui(reflections: list[dict]) -> str:
    if not reflections:
        return "No reflections found."
    lines = []
    for item in reversed(reflections):
        lines.append(
            f"When: {iso_to_readable(item.get('timestamp', ''))}\n"
            f"Person: {item.get('person_id', '')}\n"
            f"Strengths: {', '.join(item.get('strengths', [])) or 'none'}\n"
            f"Improvements: {', '.join(item.get('improvements', [])) or 'none'}\n"
            f"Tags: {', '.join(item.get('tags', [])) or 'none'}\n"
            f"Actions: {', '.join(item.get('actions', [])) or 'none'}\n"
            f"Reply preview: {item.get('ai_reply', '')[:220]}\n"
            f"{'-'*70}"
        )
    return "\n".join(lines)

def refresh_reflections_fn():
    return format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id()))

def refresh_self_model_fn():
    return format_self_model_ui(load_self_model())

# =========================================================
# WORKBENCH + READ-ONLY FILE ACCESS
# =========================================================
def list_workbench_files(limit: int = 200) -> list[str]:
    rows = []
    for p in sorted(WORKBENCH_DIR.rglob("*")):
        if p.is_file():
            try:
                rows.append(p.relative_to(WORKBENCH_DIR).as_posix())
            except Exception:
                continue
    return rows[:limit]

def format_workbench_index(limit: int = 60) -> str:
    files = list_workbench_files(limit=limit)
    if not files:
        return "Workbench is empty."
    return "\n".join(files)

def read_workbench_file(relative_path: str, max_chars: int = MAX_WORKBENCH_CHARS) -> str:
    try:
        path = safe_workbench_path(relative_path)
        if not path.exists() or not path.is_file():
            return "❌ Workbench file not found."
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed to read workbench file: {e}"

def write_workbench_file(relative_path: str, content: str, overwrite: bool = True) -> str:
    try:
        path = safe_workbench_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            return "❌ File exists and overwrite is off."
        path.write_text(content or "", encoding="utf-8")
        return f"✅ Wrote {path.relative_to(WORKBENCH_DIR).as_posix()}"
    except Exception as e:
        return f"❌ Failed to write workbench file: {e}"

def append_workbench_file(relative_path: str, content: str) -> str:
    try:
        path = safe_workbench_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content or "")
        return f"✅ Appended to {path.relative_to(WORKBENCH_DIR).as_posix()}"
    except Exception as e:
        return f"❌ Failed to append workbench file: {e}"

def read_chatlog(max_chars: int = MAX_READONLY_CHARS) -> str:
    try:
        if not CHAT_LOG_PATH.exists():
            return "chatlog.jsonl not found."
        return CHAT_LOG_PATH.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed to read chatlog: {e}"

def read_runtime_code(max_chars: int = MAX_READONLY_CHARS) -> str:
    try:
        runtime_path = BASE_DIR / "avaagent.py"
        if not runtime_path.exists():
            return "avaagent.py not found."
        return runtime_path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed to read avaagent.py: {e}"

# =========================================================
# EXPRESSION SENSING
# =========================================================
def default_expression_state() -> dict:
    return {
        "available": DEEPFACE_AVAILABLE,
        "current_expression": "unknown",
        "raw_emotion": "unknown",
        "confidence": 0.0,
        "stability": 0.0,
        "visible_face": False,
        "recognized_person_id": None,
        "history": [],
        "last_updated": now_iso(),
        "note": "DeepFace loaded" if DEEPFACE_AVAILABLE else "DeepFace unavailable"
    }

def load_expression_state() -> dict:
    if EXPRESSION_STATE_PATH.exists():
        try:
            with open(EXPRESSION_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
            base = default_expression_state()
            base.update(state or {})
            return base
        except Exception:
            pass
    return default_expression_state()

def save_expression_state(state: dict):
    try:
        with open(EXPRESSION_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Expression state save error: {e}")

def map_emotion_to_soft_signal(emotion: str) -> str:
    e = (emotion or "").lower()
    mapping = {
        "angry": "possible frustration",
        "disgust": "possible discomfort",
        "fear": "possible unease",
        "sad": "possible sadness",
        "happy": "positive affect",
        "surprise": "possible surprise",
        "neutral": "neutral expression"
    }
    return mapping.get(e, e or "unknown")

def analyze_expression(image) -> dict:
    if image is None:
        return {"ok": False, "reason": "no_image"}
    crop = extract_face_crop(image)
    if crop is None:
        return {"ok": False, "reason": "no_face"}
    if not DEEPFACE_AVAILABLE:
        return {"ok": False, "reason": "deepface_unavailable"}
    try:
        face_bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        result = DeepFace.analyze(
            img_path=face_bgr,
            actions=["emotion"],
            detector_backend="skip",
            enforce_detection=False,
            silent=True
        )
        if isinstance(result, list):
            result = result[0] if result else {}
        emotions = result.get("emotion", {}) or {}
        dominant = (result.get("dominant_emotion") or "unknown").lower()
        conf = 0.0
        if dominant and dominant in emotions:
            try:
                conf = float(emotions.get(dominant, 0.0)) / 100.0
            except Exception:
                conf = 0.0
        return {
            "ok": True,
            "raw_emotion": dominant or "unknown",
            "confidence": max(0.0, min(1.0, conf)),
            "soft_signal": map_emotion_to_soft_signal(dominant),
            "emotions": emotions
        }
    except Exception as e:
        return {"ok": False, "reason": f"analysis_error: {e}"}

def update_expression_state(image, recognized_person_id=None) -> dict:
    state = load_expression_state()
    state["available"] = DEEPFACE_AVAILABLE
    state["recognized_person_id"] = recognized_person_id
    face_visible = extract_face_crop(image) is not None
    state["visible_face"] = face_visible
    state["last_updated"] = now_iso()

    if not face_visible:
        state["current_expression"] = "unknown"
        state["raw_emotion"] = "unknown"
        state["confidence"] = 0.0
        state["stability"] = 0.0
        state["note"] = "No face visible"
        state["history"] = (state.get("history", []) or [])[-EXPRESSION_WINDOW_SIZE:]
        save_expression_state(state)
        return state

    analysis = analyze_expression(image)
    if not analysis.get("ok"):
        state["current_expression"] = "unknown"
        state["raw_emotion"] = "unknown"
        state["confidence"] = 0.0
        state["stability"] = 0.0
        reason = analysis.get("reason", "unknown")
        state["note"] = "DeepFace unavailable" if reason == "deepface_unavailable" else f"Expression unavailable: {reason}"
        save_expression_state(state)
        return state

    hist = state.get("history", []) or []
    hist.append({
        "timestamp": now_iso(),
        "raw_emotion": analysis["raw_emotion"],
        "soft_signal": analysis["soft_signal"],
        "confidence": round(float(analysis["confidence"]), 4),
        "recognized_person_id": recognized_person_id
    })
    hist = hist[-EXPRESSION_WINDOW_SIZE:]

    valid = [h for h in hist if float(h.get("confidence", 0.0)) >= EXPRESSION_MIN_CONFIDENCE]
    if valid:
        counts = {}
        for item in valid:
            counts[item["soft_signal"]] = counts.get(item["soft_signal"], 0) + 1
        best_signal, best_count = max(counts.items(), key=lambda kv: kv[1])
        matching = [h for h in valid if h["soft_signal"] == best_signal]
        avg_conf = sum(float(h.get("confidence", 0.0)) for h in matching) / max(len(matching), 1)
        stability = best_count / max(len(valid), 1)
        state["current_expression"] = best_signal
        state["raw_emotion"] = matching[-1].get("raw_emotion", "unknown")
        state["confidence"] = round(avg_conf, 4)
        state["stability"] = round(stability, 4)
        state["note"] = "Stable" if stability >= EXPRESSION_STABILITY_THRESHOLD else "Tentative"
    else:
        state["current_expression"] = "unknown"
        state["raw_emotion"] = "unknown"
        state["confidence"] = 0.0
        state["stability"] = 0.0
        state["note"] = "No stable expression yet"

    state["history"] = hist
    save_expression_state(state)
    return state

def get_expression_status_text(state: dict | None = None) -> str:
    state = state or load_expression_state()
    if not state.get("visible_face"):
        return "No visible face"
    if not DEEPFACE_AVAILABLE:
        return "Expression sensing unavailable (install DeepFace)"
    current = state.get("current_expression", "unknown")
    conf = round(float(state.get("confidence", 0.0)) * 100, 1)
    stab = round(float(state.get("stability", 0.0)) * 100, 1)
    note = state.get("note", "")
    return f"{current} | confidence {conf}% | stability {stab}% | {note}"


def default_camera_state() -> dict:
    return {
        "current": {
            "snapshot_id": "",
            "timestamp": "",
            "face_visible": False,
            "recognized_person_id": None,
            "recognized_name": "unknown",
            "recognition_text": "No face detected",
            "expression_label": "unknown",
            "expression_confidence": 0.0,
            "expression_stability": 0.0,
            "raw_emotion": "unknown",
            "importance": 0.0,
            "kept_permanently": False,
            "reason_saved": "",
            "reason_not_saved": "",
            "rolling_saved": False,
            "rolling_reason": "",
            "scene_similarity": 0.0,
            "ava_mood": "steady",
            "ava_primary_emotions": [],
            "ava_dominant_style": "neutral",
            "ava_behavior_modifiers": {},
            "comparison_summary": "",
            "comparison_tags": []
        },
        "recent_events": [],
        "last_person_id": None,
        "last_face_visible": False,
        "last_snapshot_ts": "",
        "last_saved_snapshot_ts": "",
        "last_meaningful_snapshot_ts": ""
    }


def load_camera_state() -> dict:
    if CAMERA_STATE_PATH.exists():
        try:
            with open(CAMERA_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
                base = default_camera_state()
                for k, v in base.items():
                    if k not in state:
                        state[k] = v
                return state
        except Exception as e:
            print(f"Camera state load error: {e}")
    return default_camera_state()


def save_camera_state(state: dict):
    try:
        with open(CAMERA_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Camera state save error: {e}")


def _camera_snapshot_id() -> str:
    return datetime.now().strftime("cam_%Y%m%d_%H%M%S_%f")


def _to_bgr(image):
    if image is None:
        return None
    arr = np.array(image).copy()
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.shape[-1] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return arr


def _to_rgb(image):
    if image is None:
        return None
    arr = np.array(image).copy()
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    if arr.shape[-1] == 3:
        return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return arr


def _write_image(path: Path, image) -> bool:
    try:
        bgr = _to_bgr(image)
        if bgr is None:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        return bool(cv2.imwrite(str(path), bgr))
    except Exception as e:
        print(f"Camera image write error ({path.name}): {e}")
        return False


def get_latest_annotated_snapshot_for_ui():
    try:
        if not CAMERA_LATEST_ANNOTATED_PATH.exists():
            return None
        img = cv2.imread(str(CAMERA_LATEST_ANNOTATED_PATH))
        if img is None:
            return None
        rgb = _to_rgb(img)
        if rgb is None:
            return None
        import numpy as _np_snap
        return _np_snap.array(rgb, copy=True)
    except Exception:
        return None


def _draw_face_overlay(image, state: dict):
    bgr = _to_bgr(image)
    if bgr is None:
        return None
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    except Exception:
        faces = []

    label = state.get("recognized_name") or "unknown"
    recognition_text = state.get("recognition_text", "")
    expr = state.get("expression_label", "unknown")
    ts = state.get("timestamp", "")

    for (x, y, w, h) in faces[:1]:
        cv2.rectangle(bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(bgr, label, (x, max(20, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

    overlay_lines = [
        f"Last analyzed: {iso_to_readable(ts) if ts else 'unknown'}",
        f"Face visible: {'yes' if state.get('face_visible') else 'no'}",
        f"Recognition: {recognition_text or 'unknown'}",
        f"Expression: {expr}"
    ]
    y = 24
    for line in overlay_lines:
        cv2.putText(bgr, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        y += 24
    return bgr


def _rolling_snapshot_records() -> list[Path]:
    return sorted(CAMERA_ROLLING_DIR.glob("*.json"), key=lambda q: q.stat().st_mtime)


def _prune_rolling_snapshots(limit: int = 12):
    records = _rolling_snapshot_records()
    while len(records) > limit:
        meta = records.pop(0)
        stem = meta.stem
        for target in [meta, CAMERA_ROLLING_DIR / f"{stem}_raw.jpg", CAMERA_ROLLING_DIR / f"{stem}_annotated.jpg"]:
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass


def _camera_goal_relevance_score() -> tuple[float, list[str]]:
    model = load_self_model()
    texts = list(model.get("current_goals", [])) + list(model.get("curiosity_questions", [])) + list(model.get("behavior_patterns", []))
    combined = " ".join(texts).lower()
    camera_terms = ["camera", "face", "recognition", "recognize", "expression", "visual", "vision", "see", "snapshot"]
    hits = [term for term in camera_terms if term in combined]
    return min(0.28, 0.06 * len(hits)), hits


def _read_json(path: Path, default=None):
    default = {} if default is None else default
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _rolling_snapshot_entries(limit: int = CAMERA_ROLLING_LIMIT) -> list[dict]:
    rows = []
    for meta_path in _rolling_snapshot_records()[-limit:]:
        try:
            rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def _camera_observation_text(obs: dict) -> str:
    if not obs:
        return ""
    parts = [
        f"face {'visible' if obs.get('face_visible') else 'not visible'}",
        f"identity {obs.get('recognized_name') or 'unknown'}",
        f"recognition {obs.get('recognition_text') or 'unknown'}",
        f"expression {obs.get('expression_label') or 'unknown'}",
        f"style {obs.get('ava_dominant_style') or 'neutral'}",
    ]
    return "; ".join(parts)


def _camera_expression_similarity(a: dict, b: dict) -> float:
    la = str(a.get("expression_label", "unknown") or "unknown")
    lb = str(b.get("expression_label", "unknown") or "unknown")
    if la == "unknown" or lb == "unknown":
        return 0.35 if la == lb else 0.15
    conf_a = float(a.get("expression_confidence", 0.0) or 0.0)
    conf_b = float(b.get("expression_confidence", 0.0) or 0.0)
    base = 1.0 if la == lb else 0.2
    if la in ["stress", "frustration", "confusion"] and lb in ["stress", "frustration", "confusion"]:
        base = max(base, 0.65)
    return max(0.0, min(1.0, base * (0.55 + 0.45 * ((conf_a + conf_b) / 2.0))))


def _camera_identity_similarity(a: dict, b: dict) -> float:
    if bool(a.get("face_visible")) != bool(b.get("face_visible")):
        return 0.0
    pa = a.get("recognized_person_id")
    pb = b.get("recognized_person_id")
    if pa and pb:
        return 1.0 if pa == pb else 0.0
    if not pa and not pb and bool(a.get("face_visible")) and bool(b.get("face_visible")):
        return 0.5
    return 0.2


def _camera_object_similarity(a: dict, b: dict) -> float:
    scene_a = trim_for_prompt(f"{a.get('recognition_text','')} {a.get('recognized_name','')} face {'visible' if a.get('face_visible') else 'not visible'}", limit=140)
    scene_b = trim_for_prompt(f"{b.get('recognition_text','')} {b.get('recognized_name','')} face {'visible' if b.get('face_visible') else 'not visible'}", limit=140)
    return _semantic_similarity(scene_a, scene_b)


def _camera_semantic_similarity(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    scene_similarity = _semantic_similarity(_camera_observation_text(a), _camera_observation_text(b))
    expression_similarity = _camera_expression_similarity(a, b)
    object_similarity = _camera_object_similarity(a, b)
    identity_similarity = _camera_identity_similarity(a, b)
    score = (
        0.4 * scene_similarity +
        0.25 * expression_similarity +
        0.2 * object_similarity +
        0.15 * identity_similarity
    )
    return max(0.0, min(1.0, round(score, 4)))


def _camera_expression_family(label: str) -> str:
    label = str(label or "unknown").lower()
    if label in {"stress", "frustration", "confusion", "anxiety", "fear", "angry"}:
        return "tense"
    if label in {"calm", "relaxed", "relief", "neutral"}:
        return "calm"
    if label in {"joy", "happy", "amusement", "excited"}:
        return "positive"
    if label in {"focused", "engaged", "interest", "surprise"}:
        return "engaged"
    return label or "unknown"


def _camera_family_scores(row: dict) -> dict:
    label = str(row.get("expression_label", "unknown") or "unknown")
    conf = float(row.get("expression_confidence", 0.0) or 0.0)
    fam = _camera_expression_family(label)
    tense = 0.0
    calm = 0.0
    engagement = 0.0
    if fam == "tense":
        tense = max(0.35, conf)
    elif fam == "calm":
        calm = max(0.35, conf)
    elif fam in {"engaged", "positive"}:
        engagement = max(0.35, conf)
        if fam == "positive":
            calm = max(calm, conf * 0.35)
    activity = 0.0
    act_label = str(row.get("activity_level", "unknown") or "unknown")
    if act_label == "high_change":
        activity = 1.0
    elif act_label == "moderate_change":
        activity = 0.58
    elif act_label == "still":
        activity = 0.12
    else:
        activity = 0.35 if row.get("face_visible") else 0.0
    return {
        "family": fam,
        "tense": round(tense, 4),
        "calm": round(calm, 4),
        "engagement": round(engagement, 4),
        "activity": round(activity, 4),
    }


def _camera_recent_consistency(obs: dict, rolling_entries: list[dict] | None = None) -> tuple[float, bool]:
    rolling_entries = (rolling_entries or _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT))[-VISUAL_TEMPORAL_CONSISTENCY_WINDOW:]
    if not rolling_entries:
        return 0.0, False
    families = []
    current_family = _camera_expression_family(obs.get("expression_label", "unknown"))
    contradictions = 0
    agreements = 0
    last_family = None
    for row in rolling_entries:
        fam = _camera_expression_family(row.get("expression_label", "unknown"))
        families.append(fam)
        if fam == current_family and fam not in {"unknown", "neutral"}:
            agreements += 1
        if last_family is not None and fam != last_family and fam not in {"unknown"} and last_family not in {"unknown"}:
            contradictions += 1
        last_family = fam
    temporal = agreements / max(1, len(rolling_entries))
    contradictory = False
    if len(families) >= 2:
        if families[-1] != current_family and families[-1] not in {"unknown"} and current_family not in {"unknown"}:
            contradictions += 1
        contradictory = contradictions >= max(2, len(rolling_entries)//2)
    return max(0.0, min(1.0, round(temporal, 4))), contradictory


def _camera_confidence_language_prefix(confidence: float, kind: str = "observation") -> str:
    c = float(confidence or 0.0)
    if kind == "uncertainty_observation":
        return "I'm not fully sure, but " if c >= 0.48 else "I could be off here, but "
    if c >= 0.82:
        return ""
    if c >= 0.67:
        return "It looks like "
    if c >= 0.52:
        return "I might be reading this a little cautiously, but "
    return "I could be wrong, but "


def _camera_apply_confidence_language(text: str, confidence: float, kind: str = "observation") -> str:
    base = trim_for_prompt(text or "", limit=220)
    if not base:
        return ""
    prefix = _camera_confidence_language_prefix(confidence, kind=kind)
    if not prefix:
        return base
    lowered = base[:1].lower() + base[1:] if base and base[0].isupper() else base
    return trim_for_prompt(prefix + lowered, limit=220)


def _camera_observation_confidence(obs: dict) -> float:
    face_bonus = 0.18 if obs.get("face_visible") else 0.0
    ident_bonus = 0.22 if obs.get("recognized_person_id") else 0.0
    expr_conf = float(obs.get("expression_confidence", 0.0) or 0.0)
    expr_stab = float(obs.get("expression_stability", 0.0) or 0.0)
    recogn_text = str(obs.get("recognition_text", "") or "")
    recog_conf = 0.0
    m = re.search(r"\((\d+(?:\.\d+)?)\)", recogn_text)
    if m:
        try:
            raw = float(m.group(1))
            recog_conf = max(0.0, min(1.0, 1.0 - (raw / max(1.0, FACE_RECOGNITION_THRESHOLD * 1.5))))
        except Exception:
            recog_conf = 0.0
    rolling_entries = _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT)
    temporal_consistency, contradictory = _camera_recent_consistency(obs, rolling_entries)
    recent = (rolling_entries + [obs])[-VISUAL_CONFIDENCE_SMOOTHING_WINDOW:]
    expr_values = [float(r.get("expression_confidence", 0.0) or 0.0) for r in recent if r.get("face_visible")]
    stab_values = [float(r.get("expression_stability", 0.0) or 0.0) for r in recent if r.get("face_visible")]
    smooth_expr = sum(expr_values) / max(1, len(expr_values)) if expr_values else expr_conf
    smooth_stab = sum(stab_values) / max(1, len(stab_values)) if stab_values else expr_stab
    score = 0.12 + face_bonus + ident_bonus + 0.18 * smooth_expr + 0.10 * smooth_stab + 0.08 * recog_conf + 0.22 * temporal_consistency
    if contradictory:
        score -= VISUAL_CONTRADICTION_PENALTY
    return max(0.0, min(1.0, round(score, 4)))

def _camera_expression_change(current: dict, previous: dict | None = None) -> bool:
    previous = previous or {}
    curr_label = str(current.get("expression_label", "unknown") or "unknown")
    prev_label = str(previous.get("expression_label", "unknown") or "unknown")
    curr_conf = float(current.get("expression_confidence", 0.0) or 0.0)
    prev_conf = float(previous.get("expression_confidence", 0.0) or 0.0)
    if curr_label != prev_label and (curr_conf >= 0.45 or prev_conf >= 0.45):
        return True
    return abs(curr_conf - prev_conf) >= 0.22 and curr_label not in ["unknown", "neutral"]


def _camera_time_gap_seconds(previous: dict | None = None) -> float:
    previous = previous or {}
    ts = previous.get("timestamp")
    if not ts:
        return 999999.0
    try:
        return max(0.0, now_ts() - datetime.fromisoformat(ts).timestamp())
    except Exception:
        return 999999.0


def _camera_should_store_rolling(observation: dict, previous: dict | None = None, state: dict | None = None, importance: float = 0.0, keep_event: bool = False) -> tuple[bool, str, float]:
    previous = previous or {}
    state = state or load_camera_state()
    similarity = _camera_semantic_similarity(observation, previous) if previous else 0.0
    time_gap = _camera_time_gap_seconds(previous)
    if keep_event:
        return True, "important_event", similarity
    if not previous:
        return True, "first_snapshot", similarity
    if bool(previous.get("face_visible")) != bool(observation.get("face_visible")):
        return True, "visibility_changed", similarity
    if previous.get("recognized_person_id") != observation.get("recognized_person_id"):
        return True, "identity_changed", similarity
    if _camera_expression_change(observation, previous):
        return True, "expression_changed", similarity
    if similarity < CAMERA_MEANINGFUL_SIMILARITY_THRESHOLD:
        return True, "scene_meaningfully_changed", similarity
    last_saved_ts = state.get("last_saved_snapshot_ts") or state.get("last_snapshot_ts") or ""
    age_since_saved = CAMERA_FORCE_SAVE_SECONDS + 1
    if last_saved_ts:
        try:
            age_since_saved = max(0.0, now_ts() - datetime.fromisoformat(last_saved_ts).timestamp())
        except Exception:
            pass
    if age_since_saved >= CAMERA_FORCE_SAVE_SECONDS:
        return True, "time_gap_elapsed", similarity
    return False, "redundant_recent_view", similarity


def _camera_reference_snapshot(rolling_entries: list[dict] | None = None) -> dict | None:
    rolling_entries = rolling_entries or _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT)
    if not rolling_entries:
        return None
    best = None
    best_score = -1.0
    for ref in rolling_entries:
        gap = _camera_time_gap_seconds(ref)
        if CAMERA_TEMPORAL_TARGET_GAP_MIN_SECONDS <= gap <= CAMERA_TEMPORAL_TARGET_GAP_MAX_SECONDS:
            score = 1.0 - abs(gap - ((CAMERA_TEMPORAL_TARGET_GAP_MIN_SECONDS + CAMERA_TEMPORAL_TARGET_GAP_MAX_SECONDS) / 2.0)) / max(1.0, (CAMERA_TEMPORAL_TARGET_GAP_MAX_SECONDS - CAMERA_TEMPORAL_TARGET_GAP_MIN_SECONDS))
        else:
            score = 0.2 if gap >= CAMERA_VISUAL_COMPARISON_MIN_GAP_SECONDS else -1.0
        if score > best_score:
            best_score = score
            best = ref
    return best or rolling_entries[0]


def _camera_activity_level(current: dict, reference: dict | None = None) -> str:
    reference = reference or {}
    sim = _camera_semantic_similarity(current, reference) if reference else 0.0
    if not reference:
        return "unknown"
    if sim < 0.45:
        return "high_change"
    if sim < 0.72:
        return "moderate_change"
    return "still"


def _camera_visual_pattern_summary(current: dict, rolling_entries: list[dict] | None = None) -> dict:
    rolling_entries = rolling_entries or _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT)
    if not current or not rolling_entries:
        return {"summary": "", "tags": []}
    tags = []
    summary = ""
    same_person = [r for r in rolling_entries if r.get("recognized_person_id") == current.get("recognized_person_id") and r.get("face_visible")]
    if len(same_person) >= 4:
        try:
            duration = datetime.fromisoformat(same_person[-1].get("timestamp")).timestamp() - datetime.fromisoformat(same_person[0].get("timestamp")).timestamp()
        except Exception:
            duration = 0.0
        if duration >= CAMERA_VISUAL_PATTERN_MIN_DURATION_SECONDS:
            tags.append("sustained_presence")
            summary = "The same visible person has remained at the screen for a sustained stretch."
    exprs = [_camera_expression_family(r.get("expression_label", "unknown")) for r in rolling_entries if r.get("face_visible")]
    if len(exprs) >= 4 and sum(1 for e in exprs[-4:] if e == "tense") >= 3:
        tags.append("repeated_tension")
        summary = summary or "Recent snapshots suggest repeated tension or strain in the visible expression."
    if len(rolling_entries) >= 4:
        recent = rolling_entries[-4:]
        movement_scores = []
        for i in range(1, len(recent)):
            sim = _camera_semantic_similarity(recent[i], recent[i-1])
            movement_scores.append(max(0.0, 1.0 - sim))
        avg_movement = sum(movement_scores) / max(1, len(movement_scores)) if movement_scores else 0.0
        if avg_movement <= 0.12 and current.get("face_visible"):
            tags.append("long_stillness")
            summary = summary or "You haven't moved much for a while."
        elif len(movement_scores) >= 2 and movement_scores[-1] < movement_scores[0] * 0.65 and current.get("face_visible"):
            tags.append("engagement_decay")
            summary = summary or "Your movement and expression changes have slowed down over the last few moments."
    return {"summary": summary, "tags": tags}


def _camera_temporal_comparison(current: dict, reference: dict | None = None) -> dict:
    reference = reference or {}
    summary = ""
    tags = []
    if not current or not reference:
        return {"summary": summary, "tags": tags}
    current_expr = str(current.get("expression_label", "unknown") or "unknown")
    ref_expr = str(reference.get("expression_label", "unknown") or "unknown")
    current_person = current.get("recognized_person_id")
    ref_person = reference.get("recognized_person_id")
    activity = _camera_activity_level(current, reference)
    if current_person and ref_person and current_person == ref_person:
        if ref_expr in ["frustration", "stress", "confusion"] and current_expr in ["neutral", "calm", "relaxed", "relief"]:
            summary = "You seem more relaxed now than earlier — did something change?"
            tags.append("relaxed_vs_before")
        elif current_expr != ref_expr and current_expr not in ["unknown", "neutral"]:
            summary = f"Your visible expression looks different now than it did earlier ({ref_expr} → {current_expr})."
            tags.append("expression_shift")
    if not summary and activity == "still":
        summary = "You haven't moved much for a while — are you deep in something?"
        tags.append("stillness")
    elif not summary and activity == "high_change":
        summary = "Something about the scene looks more active than earlier."
        tags.append("activity_change")
    return {"summary": summary, "tags": tags}


def _camera_transition_strength(current: dict, previous: dict | None = None) -> float:
    previous = previous or {}
    if not current or not previous:
        return 0.0
    curr_scores = _camera_family_scores(current)
    prev_scores = _camera_family_scores(previous)
    expr_delta = max(
        abs(curr_scores["tense"] - prev_scores["tense"]),
        abs(curr_scores["calm"] - prev_scores["calm"]),
        abs(curr_scores["engagement"] - prev_scores["engagement"]),
    )
    activity_delta = abs(curr_scores["activity"] - prev_scores["activity"])
    similarity_drop = max(0.0, 1.0 - _camera_semantic_similarity(current, previous))
    if bool(previous.get("face_visible")) != bool(current.get("face_visible")):
        similarity_drop = max(similarity_drop, 0.78)
    identity_change_bonus = 1.0 if previous.get("recognized_person_id") != current.get("recognized_person_id") and (previous.get("recognized_person_id") or current.get("recognized_person_id")) else 0.0
    strength = 0.36 * expr_delta + 0.24 * activity_delta + 0.25 * similarity_drop + 0.15 * identity_change_bonus
    return max(0.0, min(1.0, round(strength, 4)))

def _camera_transition_summary(current: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    summary = ""
    tags = []
    confidence = 0.0
    strength = _camera_transition_strength(current, previous)
    if not current or not previous:
        return {"summary": summary, "tags": tags, "confidence": confidence, "strength": strength}
    prev_face = bool(previous.get("face_visible"))
    curr_face = bool(current.get("face_visible"))
    prev_person = previous.get("recognized_person_id")
    curr_person = current.get("recognized_person_id")
    prev_expr = str(previous.get("expression_label", "unknown") or "unknown")
    curr_expr = str(current.get("expression_label", "unknown") or "unknown")
    prev_family = _camera_expression_family(prev_expr)
    curr_family = _camera_expression_family(curr_expr)
    prev_activity = _camera_activity_level(previous, current)
    curr_activity = _camera_activity_level(current, previous)
    if not prev_face and curr_face:
        summary = "You just came back into view."
        tags.append("returned_to_view")
        confidence = 0.8
    elif prev_face and not curr_face:
        summary = "You seem to have stepped away from the camera."
        tags.append("left_view")
        confidence = 0.78
    elif prev_person != curr_person and curr_person:
        summary = f"The visible identity looks clearer now — I think it's {current.get('recognized_name','someone')} now."
        tags.append("identity_resolved")
        confidence = 0.76
    elif prev_family == "tense" and curr_family == "calm":
        summary = "You seem more settled now than you did a moment ago."
        tags.append("stress_to_calm")
        confidence = 0.74
    elif prev_family == "calm" and curr_family == "tense":
        summary = "You look a little more strained now than you did a moment ago."
        tags.append("calm_to_stress")
        confidence = 0.7
    elif prev_activity in {"moderate_change", "high_change"} and curr_activity == "still":
        summary = "You seem to have paused after being more active a moment ago."
        tags.append("active_to_still")
        confidence = 0.66
    elif prev_activity == "still" and curr_activity in {"moderate_change", "high_change"}:
        summary = "You seem more active now than you were a moment ago."
        tags.append("still_to_active")
        confidence = 0.64
    elif prev_expr != curr_expr and curr_expr not in ["unknown", "neutral"]:
        summary = f"Your visible expression seems to have shifted toward {curr_expr.replace('_',' ')}."
        tags.append("expression_shift")
        confidence = 0.6
    if summary:
        confidence = max(0.0, min(1.0, round((confidence * 0.65) + (strength * 0.35), 4)))
    return {"summary": summary, "tags": tags, "confidence": confidence, "strength": strength}


def _camera_emotional_trend_summary(current: dict, rolling_entries: list[dict] | None = None, state: dict | None = None) -> dict:
    state = state or load_camera_state()
    rolling_entries = (rolling_entries or _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT))[-max(CAMERA_TREND_WINDOW, TREND_WINDOW):]
    summary = ""
    tags = []
    confidence = 0.0
    if len(rolling_entries) < 3:
        prev = (state.get("current", {}) or {})
        return {
            "summary": summary,
            "tags": tags,
            "confidence": confidence,
            "tension_delta": 0.0,
            "calm_delta": 0.0,
            "engagement_delta": 0.0,
            "trend_strength": 0.0,
            "trend_family": "unknown",
            "trend_persisting": False,
            "stacked_state": "",
        }

    rows = [r for r in rolling_entries if r.get("face_visible")]
    if current.get("face_visible"):
        rows = rows + [current]
    if len(rows) < 3:
        return {
            "summary": summary,
            "tags": tags,
            "confidence": confidence,
            "tension_delta": 0.0,
            "calm_delta": 0.0,
            "engagement_delta": 0.0,
            "trend_strength": 0.0,
            "trend_family": "unknown",
            "trend_persisting": False,
            "stacked_state": "",
        }

    scored = [_camera_family_scores(r) for r in rows[-max(CAMERA_TREND_WINDOW, TREND_WINDOW):]]
    recent_scored = scored[-TREND_WINDOW:]
    split = max(1, len(recent_scored)//2)
    earlier = recent_scored[:split]
    recent = recent_scored[split:]

    def avg(block, key):
        vals = [float(x.get(key, 0.0) or 0.0) for x in block]
        return sum(vals) / max(1, len(vals))

    tension_delta = avg(recent, "tense") - avg(earlier, "tense")
    calm_delta = avg(recent, "calm") - avg(earlier, "calm")
    engagement_delta = avg(recent, "engagement") - avg(earlier, "engagement")
    recent_activity = avg(recent, "activity")
    earlier_activity = avg(earlier, "activity")
    stillness_delta = max(0.0, recent_activity - earlier_activity)
    inactivity_delta = max(0.0, earlier_activity - recent_activity)

    recent_families = [x.get("family", "unknown") for x in recent_scored]
    contradictions = sum(
        1 for i in range(1, len(recent_families))
        if recent_families[i] != recent_families[i-1]
        and recent_families[i] not in {"unknown"}
        and recent_families[i-1] not in {"unknown"}
    )
    contradiction_penalty = 0.18 if contradictions >= max(2, len(recent_families)//2) else 0.0

    # current evidence from perception
    evidence = {
        "tension": max(0.0, max(tension_delta, avg(recent_scored[-4:], "tense") - 0.50)),
        "calm": max(0.0, max(calm_delta, avg(recent_scored[-4:], "calm") - 0.52)),
        "engagement": max(0.0, max(engagement_delta, avg(recent_scored[-4:], "engagement") - 0.46)),
        "drift": max(0.0, max(-engagement_delta, inactivity_delta - 0.08)),
    }

    # prior persisted trend state
    prev = (state.get("current", {}) or {})
    prev_family = str(prev.get("trend_family", "unknown") or "unknown")
    prev_strength = float(prev.get("trend_strength", 0.0) or 0.0)
    prev_ts = prev.get("timestamp") or ""
    prev_stacked = str(prev.get("stacked_state", "") or "")
    if prev_ts:
        try:
            age = max(0.0, now_ts() - datetime.fromisoformat(prev_ts).timestamp())
        except Exception:
            age = TREND_RESET_SECONDS + 1
    else:
        age = TREND_RESET_SECONDS + 1

    passive_decay = min(0.85, TREND_PASSIVE_DECAY_PER_SECOND * age)
    decayed_prev_strength = max(0.0, prev_strength - passive_decay)
    if age > TREND_RESET_SECONDS:
        decayed_prev_strength = 0.0
        prev_family = "unknown"
        prev_stacked = ""

    # blend persisted trend with new perception rather than replace immediately
    blended = dict(evidence)
    if prev_family in blended and decayed_prev_strength > 0.0:
        reinforcement = evidence.get(prev_family, 0.0)
        contradiction_signal = 0.0
        if prev_family == "tension":
            contradiction_signal = max(0.0, calm_delta)
        elif prev_family == "calm":
            contradiction_signal = max(0.0, tension_delta)
        elif prev_family == "engagement":
            contradiction_signal = max(0.0, -engagement_delta)
        elif prev_family == "drift":
            contradiction_signal = max(0.0, engagement_delta)

        persisted_component = decayed_prev_strength * TREND_BLEND_RATE
        reinforcement_component = reinforcement * TREND_REINFORCEMENT_RATE
        contradiction_component = contradiction_signal * TREND_CONTRADICTION_DECAY_RATE
        blended_prev = max(0.0, persisted_component + reinforcement_component - contradiction_component)
        blended[prev_family] = max(blended.get(prev_family, 0.0), blended_prev)

    trend_family = "unknown"
    trend_strength = 0.0
    trend_persisting = False
    stacked_state = ""

    # choose dominant family from blended evidence
    family_order = [(k, float(v or 0.0)) for k, v in blended.items()]
    family_order.sort(key=lambda kv: kv[1], reverse=True)
    if family_order and family_order[0][1] >= TREND_MIN_DELTA * 0.7:
        trend_family, trend_strength = family_order[0]

    if calm_delta >= TREND_MIN_DELTA and tension_delta <= -(TREND_MIN_DELTA * 0.8):
        summary = "You seem more relaxed now compared with a few minutes ago."
        tags.append("falling_stress")
        confidence = 0.76
        trend_family = "calm"
        trend_strength = max(trend_strength, max(abs(calm_delta), abs(tension_delta)))
    elif tension_delta >= TREND_MIN_DELTA:
        summary = "You seem a little more strained now than you did a few minutes ago."
        tags.append("rising_stress")
        confidence = 0.72
        trend_family = "tension"
        trend_strength = max(trend_strength, tension_delta)
    elif engagement_delta >= TREND_MIN_DELTA:
        summary = "You look more engaged now than you did a few minutes ago."
        tags.append("rising_engagement")
        confidence = 0.68
        trend_family = "engagement"
        trend_strength = max(trend_strength, engagement_delta)
    elif engagement_delta <= -TREND_MIN_DELTA:
        summary = "You seem a little less engaged with the screen than earlier."
        tags.append("attention_drift")
        confidence = 0.66
        trend_family = "drift"
        trend_strength = max(trend_strength, abs(engagement_delta))
    elif avg(recent_scored[-4:], "tense") >= 0.55 or blended.get("tension", 0.0) >= TREND_MIN_DELTA:
        summary = "Your visible expression has looked tense for a while."
        tags.append("sustained_tension")
        confidence = 0.64
        trend_family = trend_family if trend_family != "unknown" else "tension"
        trend_strength = max(trend_strength, blended.get("tension", avg(recent_scored[-4:], "tense")))
    elif avg(recent_scored[-4:], "calm") >= 0.58 or blended.get("calm", 0.0) >= TREND_MIN_DELTA:
        summary = "You've looked fairly steady and relaxed for a while."
        tags.append("sustained_calm")
        confidence = 0.62
        trend_family = trend_family if trend_family != "unknown" else "calm"
        trend_strength = max(trend_strength, blended.get("calm", avg(recent_scored[-4:], "calm")))

    # multi-factor stacked interpretation from persisted/blended trends
    if blended.get("tension", 0.0) >= TREND_STACKING_MIN_STRENGTH and inactivity_delta >= 0.10:
        stacked_state = "possible_frustration"
        tags.append("stacked_frustration")
        summary = summary or "You seem tense and more physically still than earlier."
        confidence = max(confidence, 0.74)
        trend_family = trend_family if trend_family != "unknown" else "tension"
        trend_strength = max(trend_strength, (blended.get("tension", 0.0) + inactivity_delta) / 2)
    elif blended.get("drift", 0.0) >= TREND_STACKING_MIN_STRENGTH and inactivity_delta >= 0.08:
        stacked_state = "possible_fatigue"
        tags.append("stacked_fatigue")
        summary = summary or "You seem less engaged and less physically active than earlier."
        confidence = max(confidence, 0.70)
        trend_family = trend_family if trend_family != "unknown" else "drift"
        trend_strength = max(trend_strength, (blended.get("drift", 0.0) + inactivity_delta) / 2)
    elif blended.get("calm", 0.0) >= TREND_STACKING_MIN_STRENGTH and blended.get("engagement", 0.0) >= TREND_STACKING_MIN_STRENGTH * 0.8:
        stacked_state = "possible_settled_focus"
        tags.append("stacked_focus")
        summary = summary or "You seem settled and steadily focused."
        confidence = max(confidence, 0.68)
        trend_family = trend_family if trend_family != "unknown" else "engagement"
        trend_strength = max(trend_strength, (blended.get("calm", 0.0) + blended.get("engagement", 0.0)) / 2)

    # persistence language if the trend is mostly being carried by previous evidence
    if not summary and prev_family != "unknown" and decayed_prev_strength >= TREND_MIN_DELTA * 0.7:
        trend_family = trend_family if trend_family != "unknown" else prev_family
        trend_strength = max(trend_strength, decayed_prev_strength)
        trend_persisting = True
        if prev_family == "tension":
            summary = "You still seem a bit tense overall."
            tags.append("persistent_tension")
        elif prev_family == "calm":
            summary = "You still look fairly settled overall."
            tags.append("persistent_calm")
        elif prev_family == "engagement":
            summary = "You still seem steadily engaged."
            tags.append("persistent_engagement")
        elif prev_family == "drift":
            summary = "You still seem a little less engaged than before."
            tags.append("persistent_drift")
        confidence = max(confidence, 0.58 * max(0.45, 1.0 - passive_decay))

    if trend_family == prev_family and trend_family != "unknown" and trend_strength > 0.0:
        trend_persisting = True

    # if perception conflicts with prior memory, transition slowly instead of replacing immediately
    if prev_family != "unknown" and trend_family != "unknown" and prev_family != trend_family and decayed_prev_strength > TREND_MIN_DELTA * 0.6:
        tags.append("trend_blended_transition")
        confidence = max(confidence, 0.60)
        trend_strength = max(trend_strength, decayed_prev_strength * 0.55)
        if not summary:
            if trend_family == "calm" and prev_family == "tension":
                summary = "You look calmer now, though I still have a little of that earlier tension in mind."
            elif trend_family == "tension" and prev_family == "calm":
                summary = "You look a bit more strained now than you did earlier."
            elif trend_family == "engagement" and prev_family == "drift":
                summary = "You seem to be re-engaging a bit now."
            elif trend_family == "drift" and prev_family == "engagement":
                summary = "You seem a little less engaged than you were earlier."

    confidence = max(0.0, min(1.0, round(confidence - contradiction_penalty, 4)))
    trend_strength = max(0.0, min(1.0, round(trend_strength, 4)))
    return {
        "summary": summary,
        "tags": tags,
        "confidence": confidence,
        "tension_delta": round(tension_delta, 4),
        "calm_delta": round(calm_delta, 4),
        "engagement_delta": round(engagement_delta, 4),
        "trend_strength": trend_strength,
        "trend_family": trend_family,
        "trend_persisting": trend_persisting,
        "stacked_state": stacked_state,
    }


def _camera_importance_decision(observation: dict, previous: dict | None = None) -> tuple[float, bool, str, str]:
    previous = previous or {}
    score = 0.0
    reasons = []
    skip_reasons = []
    current_person = observation.get("recognized_person_id")
    prev_person = previous.get("recognized_person_id")
    current_face = bool(observation.get("face_visible"))
    prev_face = bool(previous.get("face_visible"))
    similarity = _camera_semantic_similarity(observation, previous) if previous else 0.0
    time_gap = _camera_time_gap_seconds(previous)

    if current_face:
        score += 0.14
        reasons.append("face_visible")
    else:
        skip_reasons.append("no_face_visible")

    if current_person:
        score += 0.16
        reasons.append("known_person_visible")
    elif current_face:
        score += 0.10
        reasons.append("unknown_face_visible")

    if prev_person != current_person:
        score += 0.18
        reasons.append("person_changed")
    if prev_face != current_face:
        score += 0.10
        reasons.append("visibility_changed")

    expr_conf = float(observation.get("expression_confidence", 0.0) or 0.0)
    expr_label = str(observation.get("expression_label", "unknown") or "unknown")
    prev_expr = str(previous.get("expression_label", "unknown") or "unknown")
    if _camera_expression_change(observation, previous):
        score += 0.14
        reasons.append("expression_changed")
    if current_face and expr_label not in ["unknown", "neutral"] and expr_conf >= 0.60:
        score += 0.08
        reasons.append("expression_notable")

    novelty = max(0.0, 1.0 - similarity)
    score += novelty * 0.18
    if novelty >= 0.25:
        reasons.append("novel_view")
    if time_gap >= CAMERA_FORCE_SAVE_SECONDS:
        score += 0.08
        reasons.append("time_gap")

    goal_score, _goal_hits = _camera_goal_relevance_score()
    if goal_score > 0:
        score += goal_score
        reasons.append("goal_relevance")

    if current_person and current_person == OWNER_PERSON_ID:
        score += 0.06
        reasons.append("owner_present")

    # camera events become more important when Ava is already emotionally attentive
    behavior = load_mood().get("behavior_modifiers", {}) or {}
    score += max(0.0, float(behavior.get("depth", 0.5)) - 0.5) * 0.10
    score += max(0.0, float(behavior.get("initiative", 0.5)) - 0.5) * 0.08

    score = max(0.0, min(1.0, score))
    keep = score >= CAMERA_IMPORTANCE_EVENT_THRESHOLD and current_face
    if not current_face:
        keep = False
    if not keep and similarity >= CAMERA_MEANINGFUL_SIMILARITY_THRESHOLD and time_gap < CAMERA_FORCE_SAVE_SECONDS:
        skip_reasons.append("redundant_recent_view")
    if not keep and expr_label == prev_expr and current_person == prev_person and current_face == prev_face:
        skip_reasons.append("no_meaningful_change")
    reason_saved = ", ".join(dict.fromkeys(reasons))[:240] if keep else ""
    reason_not_saved = ", ".join(dict.fromkeys(skip_reasons or ["low_importance"]))[:240] if not keep else ""
    return score, keep, reason_saved, reason_not_saved

def recent_camera_events_text(limit: int = 8) -> str:
    state = load_camera_state()
    events = list(state.get("recent_events", []) or [])[-limit:]
    if not events:
        return "No important camera events saved yet."
    lines = []
    for item in reversed(events):
        ts = item.get("timestamp", "")
        face = "face visible" if item.get("face_visible") else "no face"
        ident = item.get("recognized_name") or "unknown"
        why = item.get("reason_saved", "") or item.get("reason_not_saved", "") or "no reason"
        lines.append(f"- {iso_to_readable(ts)} | {face} | {ident} | {why}")
    return "\n".join(lines)


def current_camera_memory_summary() -> str:
    st = load_camera_state().get("current", {}) or {}
    if not st:
        return "No camera memory yet."
    ts = st.get("timestamp", "")
    ident = st.get("recognized_name") or "unknown"
    recog = st.get("recognition_text", "unknown")
    expr = st.get("expression_label", "unknown")
    keep_text = "kept" if st.get("kept_permanently") else "not kept"
    why = st.get("reason_saved") or st.get("reason_not_saved") or "no reason"
    pattern = st.get("pattern_summary", "") or st.get("comparison_summary", "")
    change_reason = st.get("change_reason", "")
    transition = st.get("transition_summary", "")
    trend = st.get("trend_summary", "")
    conf = round(float(st.get("interpretation_confidence", 0.0) or 0.0) * 100, 1)
    tail = f" | Pattern: {pattern}" if pattern else ""
    tail += f" | Transition: {transition}" if transition else ""
    tail += f" | Trend: {trend}" if trend else ""
    if st.get("stacked_state"):
        tail += f" | Stacked: {st.get('stacked_state')}"
    tail += f" | Change: {change_reason}" if change_reason else ""
    tail += f" | Visual confidence: {conf}%"
    if st.get("transition_strength") is not None:
        tail += f" | Transition strength: {round(float(st.get('transition_strength',0.0) or 0.0)*100,1)}%"
    return f"Last snapshot: {iso_to_readable(ts) if ts else 'unknown'} | Face visible: {st.get('face_visible', False)} | Recognition: {recog} | Identity: {ident} | Expression: {expr} | Style: {st.get('ava_dominant_style', 'neutral')} | Rolling: {st.get('rolling_saved', False)} | Memory: {keep_text} | Why: {why}{tail}"


def get_camera_memory_status_text() -> str:
    return current_camera_memory_summary()


def process_camera_snapshot(image, recognized_text: str = "", recognized_person_id: str | None = None, expression_state: dict | None = None) -> dict:
    state = load_camera_state()
    previous = dict(state.get("current", {}) or {})
    snapshot_id = _camera_snapshot_id()
    ts = now_iso()
    face_visible = extract_face_crop(image) is not None
    recognized_name = load_profile_by_id(recognized_person_id).get("name") if recognized_person_id else "unknown"
    expr_state = expression_state or load_expression_state()
    mood = load_mood()
    current = {
        "snapshot_id": snapshot_id,
        "timestamp": ts,
        "face_visible": bool(face_visible),
        "recognized_person_id": recognized_person_id,
        "recognized_name": recognized_name if recognized_person_id else "unknown",
        "recognition_text": recognized_text or ("No face detected" if not face_visible else "Unknown face"),
        "expression_label": expr_state.get("current_expression", "unknown"),
        "expression_confidence": float(expr_state.get("confidence", 0.0) or 0.0),
        "expression_stability": float(expr_state.get("stability", 0.0) or 0.0),
        "raw_emotion": expr_state.get("raw_emotion", "unknown"),
        "ava_mood": mood.get("current_mood", "steady"),
        "ava_primary_emotions": mood.get("primary_emotions", []),
        "ava_dominant_style": mood.get("dominant_style", "neutral"),
        "ava_behavior_modifiers": mood.get("behavior_modifiers", {}),
    }
    importance, keep_event, reason_saved, reason_not_saved = _camera_importance_decision(current, previous)
    current["importance"] = importance
    current["kept_permanently"] = keep_event
    current["reason_saved"] = reason_saved
    current["reason_not_saved"] = reason_not_saved

    rolling_entries = _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT)
    comparison_reference = _camera_reference_snapshot(rolling_entries)
    comparison = _camera_temporal_comparison(current, comparison_reference)
    current["comparison_summary"] = comparison.get("summary", "")
    current["comparison_tags"] = comparison.get("tags", [])
    transition = _camera_transition_summary(current, previous)
    current["transition_summary"] = transition.get("summary", "")
    current["transition_tags"] = transition.get("tags", [])
    trend = _camera_emotional_trend_summary(current, rolling_entries, state=state)
    current["trend_summary"] = trend.get("summary", "")
    current["trend_tags"] = trend.get("tags", [])
    current["trend_tension_delta"] = float(trend.get("tension_delta", 0.0) or 0.0)
    current["trend_calm_delta"] = float(trend.get("calm_delta", 0.0) or 0.0)
    current["trend_engagement_delta"] = float(trend.get("engagement_delta", 0.0) or 0.0)
    current["trend_strength"] = float(trend.get("trend_strength", 0.0) or 0.0)
    current["trend_family"] = trend.get("trend_family", "unknown") or "unknown"
    current["trend_persisting"] = bool(trend.get("trend_persisting", False))
    current["stacked_state"] = trend.get("stacked_state", "") or ""
    pattern_summary = _camera_visual_pattern_summary(current, rolling_entries)
    current["pattern_summary"] = pattern_summary.get("summary", "")
    current["pattern_tags"] = pattern_summary.get("tags", [])
    rolling_for_conf = (rolling_entries + [current])[-VISUAL_CONFIDENCE_SMOOTHING_WINDOW:]
    frame_confs = [_camera_observation_confidence(x) for x in rolling_for_conf]
    smoothed_conf = sum(frame_confs) / max(1, len(frame_confs)) if frame_confs else _camera_observation_confidence(current)
    current["interpretation_confidence"] = max(
        round(smoothed_conf, 4),
        float(transition.get("confidence", 0.0) or 0.0),
        float(trend.get("confidence", 0.0) or 0.0),
    )
    current["transition_strength"] = float(transition.get("strength", 0.0) or 0.0)
    current["action_confidence"] = max(0.0, min(1.0, round(current["interpretation_confidence"] * 0.74 + current["transition_strength"] * 0.18, 4)))

    save_to_rolling, rolling_reason, similarity = _camera_should_store_rolling(current, previous, state=state, importance=importance, keep_event=keep_event)
    current["change_reason"] = reason_saved if keep_event else rolling_reason
    current["rolling_saved"] = bool(save_to_rolling)
    current["rolling_reason"] = rolling_reason
    current["scene_similarity"] = round(float(similarity), 3)

    if image is not None:
        _write_image(CAMERA_LATEST_RAW_PATH, image)
        annotated = _draw_face_overlay(image, current)
        if annotated is not None:
            cv2.imwrite(str(CAMERA_LATEST_ANNOTATED_PATH), annotated)
        with open(CAMERA_LATEST_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        if save_to_rolling:
            base = snapshot_id
            _write_image(CAMERA_ROLLING_DIR / f"{base}_raw.jpg", image)
            annotated = _draw_face_overlay(image, current)
            if annotated is not None:
                cv2.imwrite(str(CAMERA_ROLLING_DIR / f"{base}_annotated.jpg"), annotated)
            with open(CAMERA_ROLLING_DIR / f"{base}.json", "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            _prune_rolling_snapshots(limit=CAMERA_ROLLING_LIMIT)
            state["last_saved_snapshot_ts"] = ts

    if keep_event and image is not None:
        _write_image(CAMERA_EVENTS_DIR / f"{snapshot_id}_raw.jpg", image)
        annotated = _draw_face_overlay(image, current)
        if annotated is not None:
            cv2.imwrite(str(CAMERA_EVENTS_DIR / f"{snapshot_id}_annotated.jpg"), annotated)
        with open(CAMERA_EVENTS_DIR / f"{snapshot_id}.json", "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        person_for_memory = recognized_person_id or get_active_person_id()
        summary = (
            f"Camera observation at {ts}: face_visible={current['face_visible']}, recognition={current['recognition_text']}, "
            f"identity={current['recognized_name']}, expression={current['expression_label']}, ava_mood={current['ava_mood']}, "
            f"ava_style={current['ava_dominant_style']}, reason_saved={reason_saved}, transition={current.get('transition_summary','')}, trend={current.get('trend_summary','')}."
        )
        remember_memory(summary, person_id=person_for_memory, category="camera_event", importance=importance, source="camera_perception", tags=["camera", "snapshot", "vision", "visual_memory"])

        event_summary = {
            "timestamp": ts,
            "snapshot_id": snapshot_id,
            "face_visible": current["face_visible"],
            "recognized_person_id": current["recognized_person_id"],
            "recognized_name": current["recognized_name"],
            "recognition_text": current["recognition_text"],
            "expression_label": current["expression_label"],
            "importance": importance,
            "reason_saved": reason_saved,
            "comparison_summary": current.get("comparison_summary", ""),
            "image_path": str(CAMERA_EVENTS_DIR / f"{snapshot_id}_annotated.jpg")
        }
        recent = list(state.get("recent_events", []) or [])
        recent.append(event_summary)
        state["recent_events"] = recent[-24:]
        state["last_meaningful_snapshot_ts"] = ts
        try:
            event_jsons = sorted(CAMERA_EVENTS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime)
            excess = max(0, len(event_jsons) - CAMERA_EVENT_RETENTION_LIMIT)
            for meta_path in event_jsons[:excess]:
                stem = meta_path.stem
                for suffix in [".json", "_raw.jpg", "_annotated.jpg"]:
                    target = CAMERA_EVENTS_DIR / f"{stem}{suffix}" if suffix == ".json" else CAMERA_EVENTS_DIR / f"{stem}{suffix}"
                    if target.exists():
                        try:
                            target.unlink()
                        except Exception:
                            pass
        except Exception:
            pass

        if (current.get("comparison_summary") or current.get("transition_summary") or current.get("trend_summary") or current.get("pattern_summary")) and importance >= 0.72:
            reflection_text = trim_for_prompt((current.get("trend_summary") or current.get("transition_summary") or current.get("comparison_summary") or current.get("pattern_summary") or ""), limit=220)
            if reflection_text:
                reflect_on_last_reply(
                    user_input=f"[visual observation] {reflection_text}",
                    ai_reply=f"I noticed visually: {reflection_text}",
                    person_id=person_for_memory,
                    actions=["camera_reflection_trigger"]
                )

    state["current"] = current
    state["last_person_id"] = current.get("recognized_person_id")
    state["last_face_visible"] = current.get("face_visible")
    state["last_snapshot_ts"] = ts
    save_camera_state(state)
    return current

def expression_prompt_text(state: dict | None = None) -> str:
    state = state or load_expression_state()
    if not state.get("visible_face"):
        return "No face is currently visible, so there is no usable expression signal."
    if not DEEPFACE_AVAILABLE:
        return "Expression sensing is unavailable right now. Do not infer feelings from facial expressions."
    current = state.get("current_expression", "unknown")
    raw = state.get("raw_emotion", "unknown")
    conf = round(float(state.get("confidence", 0.0)) * 100, 1)
    stab = round(float(state.get("stability", 0.0)) * 100, 1)
    note = state.get("note", "")
    return f"Observed facial expression suggests {current} (raw emotion: {raw}, confidence {conf}%, stability {stab}%). Treat this only as soft context, not certain knowledge. Status: {note}."

# =========================================================
# AUTONOMOUS INITIATIVE
# =========================================================
def default_initiative_state() -> dict:
    return {
        "last_face_seen_ts": 0.0,
        "last_interaction_ts": 0.0,
        "last_initiation_ts": 0.0,
        "last_initiation_message": "",
        "last_initiated_topic": "",
        "last_presence_reason": "none",
        "presence_score": 0.0,
        "last_busy_score": 0.0,
        "recent_initiated_topics": {},
        "recent_initiated_texts": [],
        "recent_candidate_kinds": [],
        "recent_active_goals": [],
        "pending_initiation": None,
        "initiative_history": [],
        "consecutive_ignored_initiations": 0,
        "last_user_message_length": 0,
        "last_user_response_brief": False,
        "interaction_energy": 0.58
    }

def load_initiative_state() -> dict:
    if INITIATIVE_STATE_PATH.exists():
        try:
            with open(INITIATIVE_STATE_PATH, "r", encoding="utf-8") as f:
                base = default_initiative_state()
                loaded = json.load(f)
                base.update(loaded if isinstance(loaded, dict) else {})
                return base
        except Exception:
            pass
    return default_initiative_state()

def save_initiative_state(state: dict):
    try:
        with open(INITIATIVE_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Initiative state save error: {e}")

def initiative_status_text(state: dict | None = None) -> str:
    state = state or load_initiative_state()
    pending = state.get("pending_initiation") or {}
    if pending and pending.get("text"):
        return f"Last autonomous message: {trim_for_prompt(pending.get('text',''), limit=110)}"
    if state.get("last_initiation_message"):
        return f"Last autonomous message: {trim_for_prompt(state.get('last_initiation_message',''), limit=110)}"
    return "No autonomous message yet."

def _decayed_recent_score(age_seconds: float, window_seconds: float) -> float:
    if age_seconds <= 0:
        return 1.0
    if age_seconds >= window_seconds:
        return 0.0
    return max(0.0, 1.0 - (age_seconds / window_seconds))

def _topic_key(text: str) -> str:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]
    return "_".join(tokens[:8]) or slugify_name(text[:32])

_EMBED_SIM_CACHE: dict[str, list[float]] = {}
_EMBED_SIM_READY = None

def _token_jaccard(a: str, b: str) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta or not tb:
        return 0.0
    overlap = len(ta.intersection(tb))
    union = len(ta.union(tb))
    return overlap / max(1, union)


def _cosine_similarity(vec_a, vec_b) -> float:
    try:
        dot = sum(float(x) * float(y) for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(float(x) * float(x) for x in vec_a))
        norm_b = math.sqrt(sum(float(y) * float(y) for y in vec_b))
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    except Exception:
        return 0.0


def _get_similarity_embedder():
    global _EMBED_SIM_READY
    if _EMBED_SIM_READY is False:
        return None
    try:
        if _EMBED_SIM_READY is None:
            _EMBED_SIM_READY = OllamaEmbeddings(model=EMBED_MODEL)
        return _EMBED_SIM_READY
    except Exception:
        _EMBED_SIM_READY = False
        return None


def _embed_text_cached(text: str):
    key = trim_for_prompt(text or '', limit=300)
    if not key:
        return None
    cached = _EMBED_SIM_CACHE.get(key)
    if cached is not None:
        return cached
    embedder = _get_similarity_embedder()
    if embedder is None:
        return None
    try:
        vec = embedder.embed_query(key)
        if len(_EMBED_SIM_CACHE) >= 256:
            try:
                _EMBED_SIM_CACHE.pop(next(iter(_EMBED_SIM_CACHE)))
            except Exception:
                _EMBED_SIM_CACHE.clear()
        _EMBED_SIM_CACHE[key] = vec
        return vec
    except Exception:
        return None


def _semantic_similarity(a: str, b: str) -> float:
    lexical = _token_jaccard(a, b)
    vec_a = _embed_text_cached(a)
    vec_b = _embed_text_cached(b)
    if vec_a is not None and vec_b is not None:
        emb = (_cosine_similarity(vec_a, vec_b) + 1.0) / 2.0
        return max(0.0, min(1.0, round(0.75 * emb + 0.25 * lexical, 4)))
    return lexical

def _kind_cooldown_seconds(kind: str) -> int:
    return int(INITIATIVE_KIND_COOLDOWNS.get(kind, INITIATIVE_TOPIC_COOLDOWN_SECONDS))

def expire_stale_pending_initiation(state: dict | None = None) -> dict:
    state = state or load_initiative_state()
    pending = state.get("pending_initiation") or {}
    if not pending or not pending.get("ts"):
        return state
    now = now_ts()
    age = now - float(pending.get("ts", 0.0) or 0.0)
    if age >= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS and not pending.get("responded"):
        state["consecutive_ignored_initiations"] = int(state.get("consecutive_ignored_initiations", 0) or 0) + 1
        energy = float(state.get("interaction_energy", 0.58) or 0.58)
        state["interaction_energy"] = round(max(0.12, energy - 0.12), 3)
        history = state.get("initiative_history", []) or []
        history.append({
            "timestamp": now_iso(),
            "topic_key": pending.get("topic_key", ""),
            "text": pending.get("text", ""),
            "candidate_kind": pending.get("candidate_kind", "thought"),
            "responded": False,
            "expired_without_response": True
        })
        state["initiative_history"] = history[-60:]
        state["pending_initiation"] = None
        save_initiative_state(state)
    return state

def update_presence_state(face_visible: bool, recognized_person_id: str | None = None, interaction_happened: bool = False) -> dict:
    state = load_initiative_state()
    now = now_ts()
    if face_visible:
        state["last_face_seen_ts"] = now
    if interaction_happened:
        state["last_interaction_ts"] = now
    face_score = _decayed_recent_score(now - float(state.get("last_face_seen_ts", 0.0)), PRESENCE_FACE_WINDOW_SECONDS)
    interaction_score = _decayed_recent_score(now - float(state.get("last_interaction_ts", 0.0)), PRESENCE_INTERACTION_WINDOW_SECONDS)
    presence_score = min(1.0, (face_score * 0.65) + (interaction_score * 0.5))
    state["presence_score"] = round(presence_score, 4)
    if face_score > 0.2 and interaction_score > 0.15:
        state["last_presence_reason"] = "face_and_recent_interaction"
    elif face_score > 0.2:
        state["last_presence_reason"] = "face_seen_recently"
    elif interaction_score > 0.15:
        state["last_presence_reason"] = "recent_interaction"
    else:
        state["last_presence_reason"] = "not_present"
    if recognized_person_id:
        state["last_seen_person_id"] = recognized_person_id
    save_initiative_state(state)
    return state

def note_user_interaction_for_initiative(user_text: str = "", interaction_kind: str = "text") -> dict:
    state = expire_stale_pending_initiation(update_presence_state(False, interaction_happened=True))
    now = now_ts()
    preview = trim_for_prompt(user_text, limit=120)
    state["last_user_message_length"] = len((user_text or "").strip())
    state["last_user_response_brief"] = bool((user_text or "").strip()) and len((user_text or "").strip()) <= 16
    pending = state.get("pending_initiation")
    if pending and pending.get("ts") and (now - float(pending.get("ts", 0.0))) <= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS:
        pending["responded"] = True
        pending["response_kind"] = interaction_kind
        pending["response_ts"] = now
        pending["response_preview"] = preview
        history = state.get("initiative_history", [])
        history.append({
            "timestamp": now_iso(),
            "topic_key": pending.get("topic_key", ""),
            "text": pending.get("text", ""),
            "candidate_kind": pending.get("candidate_kind", "thought"),
            "responded": True,
            "response_kind": interaction_kind
        })
        state["initiative_history"] = history[-60:]
        state["pending_initiation"] = None
        state["consecutive_ignored_initiations"] = 0
        energy = float(state.get("interaction_energy", 0.58) or 0.58)
        state["interaction_energy"] = round(min(0.95, energy + 0.08), 3)
    else:
        energy = float(state.get("interaction_energy", 0.58) or 0.58)
        state["interaction_energy"] = round(min(0.95, energy + 0.02), 3)
    save_initiative_state(state)
    return state

def estimate_user_busy_score(state: dict | None = None, expression_state: dict | None = None) -> float:
    state = expire_stale_pending_initiation(state or load_initiative_state())
    now = now_ts()
    quiet_for = now - float(state.get("last_interaction_ts", 0.0) or 0.0)
    score = 0.0
    if quiet_for < 45:
        score += 0.72
    elif quiet_for < 90:
        score += 0.60
    elif quiet_for < INITIATIVE_INACTIVITY_SECONDS:
        score += 0.35
    pending = state.get("pending_initiation") or {}
    if pending and pending.get("ts") and (now - float(pending.get("ts", 0.0))) < INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS:
        score = max(score, 0.82)
    if bool(state.get("last_user_response_brief", False)) and quiet_for < 240:
        score += 0.10
    ignored = int(state.get("consecutive_ignored_initiations", 0) or 0)
    if ignored >= 2:
        score += min(0.18, 0.06 * ignored)
    expr = expression_state or load_expression_state()
    current_expr = (expr.get("current_expression") or "").lower()
    if any(x in current_expr for x in ["frustration", "stress", "confusion"]):
        score += 0.18
    return min(1.0, round(score, 3))


def _camera_visual_candidates(person_id: str) -> list[dict]:
    candidates = []
    camera_state = load_camera_state()
    current = camera_state.get("current", {}) or {}
    rolling = _rolling_snapshot_entries(limit=CAMERA_ROLLING_LIMIT)
    if not current:
        return candidates
    visual_conf = float(current.get("interpretation_confidence", 0.0) or 0.0)
    transition_strength = float(current.get("transition_strength", 0.0) or 0.0)
    initiative_state = load_initiative_state()
    recent_texts = initiative_state.get("recent_initiated_texts", []) or []
    now = now_ts()

    def recently_said_similar(raw: str, family: str = "") -> bool:
        raw = trim_for_prompt(raw, limit=180)
        if not raw:
            return True
        for row in recent_texts[-SEMANTIC_TOPIC_RECENT_LIMIT:]:
            age = max(0.0, now - float(row.get("ts", 0.0) or 0.0))
            if age > VISUAL_REPETITION_SUPPRESSION_SECONDS:
                continue
            sim = _semantic_similarity(raw, row.get("text", ""))
            if sim >= VISUAL_REPETITION_SIMILARITY_THRESHOLD:
                return True
            if family and row.get("kind") in ["visual_observation", "transition_observation", "engagement_observation", "attention_drift", "visual_pattern", "visual_checkin"]:
                low = row.get("text", "").lower()
                if family in low:
                    return True
        return False

    def add_candidate(kind: str, txt: str, base: float, mem_imp: float | None = None, extra_conf: float | None = None, action_boost: float = 0.0, family: str = ""):
        raw = trim_for_prompt(txt, limit=180)
        if not raw or recently_said_similar(raw, family=family):
            return
        interp_conf = max(visual_conf, float(extra_conf or 0.0))
        cleaned = _camera_apply_confidence_language(raw, interp_conf, kind=kind)
        action_conf = max(0.0, min(1.0, round(interp_conf * 0.72 + transition_strength * 0.18 + action_boost, 4)))
        candidates.append({
            "kind": kind,
            "text": cleaned,
            "topic_key": _topic_key(raw),
            "base_score": base,
            "memory_importance": max(0.5, float(mem_imp if mem_imp is not None else current.get("importance", 0.5))),
            "interpretation_confidence": interp_conf,
            "action_confidence": action_conf,
        })

    trend_family = str(current.get("trend_family", "unknown") or "unknown")
    if current.get("transition_summary"):
        add_candidate("transition_observation", current.get("transition_summary", ""), min(0.9, 0.64 + float(current.get("importance", 0.5)) * 0.2), extra_conf=max(0.66, transition_strength), action_boost=0.06 if transition_strength >= VISUAL_TRANSITION_INITIATION_THRESHOLD else -0.03, family="transition")
    if current.get("trend_summary"):
        add_candidate("visual_observation", current.get("trend_summary", ""), min(0.9, 0.68 + float(current.get("importance", 0.5)) * 0.18), extra_conf=max(0.66, float(current.get("interpretation_confidence", 0.0) or 0.0)), action_boost=0.04, family=trend_family)
    if current.get("comparison_summary"):
        add_candidate("visual_observation", current.get("comparison_summary", ""), min(0.86, 0.64 + float(current.get("importance", 0.5)) * 0.18), extra_conf=0.62, family="comparison")
    if current.get("pattern_summary"):
        add_candidate("visual_pattern", current.get("pattern_summary", ""), min(0.84, 0.62 + float(current.get("importance", 0.5)) * 0.16), extra_conf=0.6, family="pattern")

    if len(rolling) >= 4:
        same_person = [r for r in rolling if r.get("recognized_person_id") == person_id and r.get("face_visible")]
        if len(same_person) >= 4:
            try:
                first_ts = datetime.fromisoformat(same_person[0].get("timestamp")).timestamp()
                last_ts = datetime.fromisoformat(same_person[-1].get("timestamp")).timestamp()
                duration = max(0.0, last_ts - first_ts)
            except Exception:
                duration = 0.0
            if duration >= CAMERA_VISUAL_PATTERN_MIN_DURATION_SECONDS:
                add_candidate("engagement_observation", "You've been focused on that for a while — how's it going?", 0.74, 0.72, 0.66, action_boost=0.05, family="focus")

    if current.get("face_visible") and current.get("recognized_person_id") == person_id and current.get("expression_label") in ["frustration", "stress", "confusion"] and float(current.get("expression_confidence", 0.0) or 0.0) >= 0.55:
        add_candidate("visual_checkin", "You seem a little strained right now — want to stay with this, or shift gears for a second?", 0.78, max(0.70, float(current.get("importance", 0.5))), 0.72, action_boost=0.06, family="tension")

    if current.get("face_visible") and not current.get("recognized_person_id") and visual_conf >= 0.5:
        add_candidate("uncertainty_observation", "I can see someone clearly, but I'm still not confident about who it is yet.", 0.66, 0.62, 0.58, family="uncertainty")

    if current.get("face_visible") and current.get("recognized_person_id") == person_id and current.get("rolling_reason") == "redundant_recent_view":
        add_candidate("attention_drift", "You haven't moved much for a while — are you deep in something, or just paused?", 0.68, 0.6, 0.56, family="stillness")

    return candidates

def collect_initiative_candidates(person_id: str) -> list[dict]:
    model = load_self_model()
    reflections = load_recent_reflections(limit=18, person_id=person_id)
    memories = list_recent_memories(person_id, limit=18)
    recent_chat = load_recent_chat(limit=18, person_id=person_id)
    initiative_state = load_initiative_state()
    candidates = []
    seen = set()

    structured_goals = top_active_goals(limit=16, context_text=" ".join(r.get("content", "") for r in recent_chat[-6:]), mood=load_mood())
    for g in structured_goals:
        cleaned = trim_for_prompt(g.get("text", ""), limit=180)
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        kind = "curiosity_question" if g.get("kind") == "question" else "current_goal"
        base = 0.60 + 0.34 * float(g.get("current_priority", 0.5))
        mem = 0.46 + 0.44 * float(g.get("importance", 0.5))
        candidates.append({
            "kind": kind,
            "text": cleaned,
            "topic_key": _topic_key(cleaned),
            "base_score": min(0.97, base),
            "memory_importance": min(0.97, mem),
            "goal_id": g.get("goal_id", ""),
            "goal_horizon": g.get("horizon", "short_term"),
            "goal_priority": float(g.get("current_priority", 0.5)),
        })

    for row in reversed(reflections):
        cleaned = trim_for_prompt(row.get("summary", ""), limit=180)
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        refl_importance = max(0.58, min(0.97, float(row.get("importance", 0.62))))
        candidates.append({
            "kind": "recent_reflection",
            "text": cleaned,
            "topic_key": _topic_key(cleaned),
            "base_score": refl_importance,
            "memory_importance": refl_importance,
            "source_reflection_id": row.get("reflection_id", "")
        })

    for row in memories[:10]:
        meta = row.get("metadata", {}) or {}
        raw_text = (meta.get("raw_text") or row.get("text", "") or "").strip()
        cleaned = trim_for_prompt(raw_text, limit=180)
        if not cleaned or cleaned.lower() in seen:
            continue
        importance = float(meta.get("importance_pct", meta.get("importance_score", 0.0)) or 0.0)
        if importance < 0.74:
            continue
        seen.add(cleaned.lower())
        candidates.append({
            "kind": "salient_memory",
            "text": cleaned,
            "topic_key": _topic_key(cleaned),
            "base_score": min(0.96, max(0.74, importance)),
            "memory_importance": importance,
            "source_memory_id": row.get("memory_id", "")
        })

    token_counts = {}
    for row in recent_chat[-12:]:
        for tok in _token_set(row.get("content", "")):
            if len(tok) >= 4:
                token_counts[tok] = token_counts.get(tok, 0) + 1
    repeated = [tok for tok, count in sorted(token_counts.items(), key=lambda x: x[1], reverse=True) if count >= 3][:3]
    if repeated:
        theme_text = f"We keep circling back to {', '.join(repeated)} lately. Should we stay with that, or shift direction a little?"
        if theme_text.lower() not in seen:
            candidates.append({
                "kind": "pattern_checkin",
                "text": theme_text,
                "topic_key": _topic_key(theme_text),
                "base_score": 0.73,
                "memory_importance": 0.70
            })

    for cand in _camera_visual_candidates(person_id):
        if cand.get("text", "").lower() in seen:
            continue
        seen.add(cand.get("text", "").lower())
        candidates.append(cand)

    if int(initiative_state.get("consecutive_ignored_initiations", 0) or 0) >= 2:
        feedback_text = "I can ease off a bit if you want — should I keep bringing things up on my own, or would you rather lead for a while?"
        if feedback_text.lower() not in seen:
            candidates.append({
                "kind": "feedback_guidance",
                "text": feedback_text,
                "topic_key": _topic_key(feedback_text),
                "base_score": 0.84,
                "memory_importance": 0.82
            })

    return candidates

def _goal_kind_preferences(goal_name: str) -> dict:
    prefs = {
        "reduce_stress": {"preferred_kinds": {"visual_checkin", "feedback_guidance", "transition_observation", "visual_observation"}, "avoid_kinds": {"curiosity_question"}, "keyword_bias": ["relaxed", "strained", "stress", "calm", "ease", "pause"]},
        "increase_engagement": {"preferred_kinds": {"curiosity_question", "engagement_observation", "attention_drift", "pattern_checkin"}, "avoid_kinds": {"visual_checkin"}, "keyword_bias": ["curious", "shift", "going", "thought", "interesting"]},
        "explore_topic": {"preferred_kinds": {"curiosity_question", "current_goal", "recent_reflection", "salient_memory"}, "avoid_kinds": set(), "keyword_bias": ["explore", "wonder", "thinking", "earlier", "build", "version"]},
        "clarify": {"preferred_kinds": {"current_goal", "feedback_guidance", "uncertainty_observation", "recent_reflection"}, "avoid_kinds": {"attention_drift"}, "keyword_bias": ["clarify", "understand", "unsure", "not confident", "figure out"]},
        "maintain_connection": {"preferred_kinds": {"pattern_checkin", "curiosity_question", "visual_observation"}, "avoid_kinds": set(), "keyword_bias": ["how's it going", "earlier", "thinking", "together"]},
        "observe_silently": {"preferred_kinds": set(), "avoid_kinds": {"visual_checkin", "feedback_guidance", "curiosity_question", "pattern_checkin", "engagement_observation", "attention_drift", "visual_observation", "transition_observation"}, "keyword_bias": []},
        "wait_for_user": {"preferred_kinds": set(), "avoid_kinds": {"visual_checkin", "feedback_guidance", "curiosity_question", "pattern_checkin", "engagement_observation", "attention_drift", "visual_observation", "transition_observation"}, "keyword_bias": []},
    }
    return prefs.get(goal_name or "", {"preferred_kinds": set(), "avoid_kinds": set(), "keyword_bias": []})

def _candidate_goal_alignment_score(candidate: dict, active_goal_name: str, goal_blend_names: list[str] | None = None) -> float:
    goal_blend_names = goal_blend_names or []
    score = 0.0
    text_l = (candidate.get("text") or "").lower()
    kind = candidate.get("kind", "thought")
    for idx, goal_name in enumerate([active_goal_name] + [g for g in goal_blend_names if g and g != active_goal_name]):
        if not goal_name:
            continue
        prefs = _goal_kind_preferences(goal_name)
        weight = 1.0 if idx == 0 else 0.45
        if kind in prefs["preferred_kinds"]:
            score += 0.18 * weight
        if kind in prefs["avoid_kinds"]:
            score -= 0.28 * weight
        if any(kw in text_l for kw in prefs["keyword_bias"]):
            score += 0.08 * weight
    return score


def _silence_candidate(reason: str = "holding back") -> dict:
    return {
        "kind": "do_nothing",
        "text": "",
        "topic_key": "do_nothing",
        "base_score": DO_NOTHING_BASE_SCORE,
        "memory_importance": 0.30,
        "score": DO_NOTHING_BASE_SCORE,
        "reason": reason,
        "silent_candidate": True,
        "goal_alignment": 0.0,
        "action_confidence": 1.0,
        "interpretation_confidence": 1.0,
    }


def _hard_gate_candidate(candidate: dict, state: dict, active_goal_name: str, goal_blend_names: list[str] | None = None, goal_strength: float = 0.0, busy_score: float = 0.0) -> tuple[bool, str]:
    goal_blend_names = goal_blend_names or []
    kind = str(candidate.get("kind", "thought"))
    if kind == "do_nothing":
        candidate["gate_reason"] = "silence_candidate"
        return True, "silence_candidate"
    if active_goal_name in ["observe_silently", "wait_for_user"]:
        candidate["gate_reason"] = f"silent_goal:{active_goal_name}"
        return False, f"silent_goal:{active_goal_name}"
    align = _candidate_goal_alignment_score(candidate, active_goal_name, goal_blend_names) if active_goal_name else 0.0
    candidate["goal_alignment"] = align
    action_conf = float(candidate.get("action_confidence", candidate.get("interpretation_confidence", 0.0)) or 0.0)
    importance_score = float(candidate.get("memory_importance", candidate.get("base_score", candidate.get("score", 0.0))) or 0.0)
    candidate["importance_score"] = round(importance_score, 3)
    candidate["confidence_score"] = round(action_conf, 3)
    candidate["goal_alignment_score"] = round(align, 3)

    severe_goal_conflict = active_goal_name and goal_strength >= STRONG_GOAL_THRESHOLD and align <= HARD_GOAL_MISALIGN_THRESHOLD and action_conf < 0.88 and importance_score < 0.82
    if severe_goal_conflict:
        candidate["gate_reason"] = "goal_misaligned"
        return False, "goal_misaligned"
    if kind in ["visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift", "visual_pattern", "visual_checkin"] and action_conf < VISUAL_INITIATIVE_ACTION_CONFIDENCE_THRESHOLD:
        candidate["gate_reason"] = "low_action_confidence"
        return False, "low_action_confidence"
    recent_kinds = state.get("recent_candidate_kinds", []) or []
    now = now_ts()
    very_recent_same_kind = [r for r in recent_kinds if r.get("kind") == kind and (now - float(r.get("ts", 0.0) or 0.0)) <= RECENT_BEHAVIOR_HARD_BLOCK_SECONDS]
    if len(very_recent_same_kind) >= 2 and kind in ["feedback_guidance", "visual_checkin", "visual_observation", "transition_observation", "uncertainty_observation"] and importance_score < 0.9:
        candidate["gate_reason"] = "hard_repeat_block"
        return False, "hard_repeat_block"
    if busy_score > 0.90 and kind not in ["feedback_guidance"] and action_conf < 0.85 and importance_score < 0.88:
        candidate["gate_reason"] = "too_busy"
        return False, "too_busy"
    candidate["gate_reason"] = "ok"
    return True, "ok"

def _apply_soft_choice_penalties(candidates: list[dict], state: dict, active_goal_name: str, goal_blend_names: list[str] | None = None, goal_strength: float = 0.0) -> list[dict]:
    goal_blend_names = goal_blend_names or []
    now = now_ts()
    recent_kinds = state.get("recent_candidate_kinds", []) or []
    recent_texts = state.get("recent_initiated_texts", []) or []
    recent_types = [str(r.get("kind", "")) for r in recent_kinds[-6:] if r.get("kind")]
    mood = load_mood()
    behavior = (mood.get("behavior_modifiers", {}) or {})
    stressed_context = float(behavior.get("caution", 0.5) or 0.5) > 0.64
    for cand in candidates:
        score = float(cand.get("score", cand.get("base_score", 0.0)) or 0.0)
        kind = str(cand.get("kind", "thought"))
        align = float(cand.get("goal_alignment", _candidate_goal_alignment_score(cand, active_goal_name, goal_blend_names) if active_goal_name else 0.0) or 0.0)
        penalties_applied = []
        boosts_applied = []
        total_penalty = 0.0
        total_boost = 0.0
        if active_goal_name and align < 0:
            penalty = min(SOFT_GOAL_MISALIGN_PENALTY, abs(align) * 0.35)
            total_penalty += penalty
            penalties_applied.append(("goal_misalign", round(penalty, 3)))
        elif active_goal_name and align > 0.20:
            boost = STRONG_GOAL_ALIGNMENT_BOOST if align > 0.35 else MODERATE_GOAL_ALIGNMENT_BOOST
            total_boost += boost
            boosts_applied.append(("goal_align", round(boost, 3)))
        soft_repeat = sum(1 for r in recent_kinds if r.get("kind") == kind and (now - float(r.get("ts", 0.0) or 0.0)) <= RECENT_BEHAVIOR_SOFT_PENALTY_SECONDS)
        if soft_repeat:
            penalty = min(SOFT_PENALTY_MAJOR, SOFT_PENALTY_MINOR * soft_repeat)
            total_penalty += penalty
            penalties_applied.append(("recent_kind_repeat", round(penalty, 3)))
        ctext = str(cand.get("text", ""))
        for r in recent_texts[-6:]:
            if (now - float(r.get("ts", 0.0) or 0.0)) > RECENT_BEHAVIOR_SOFT_PENALTY_SECONDS:
                continue
            sim = _semantic_similarity(ctext, str(r.get("text", ""))) if ctext else 0.0
            if sim >= 0.82:
                penalty = SOFT_PENALTY_MAJOR
                total_penalty += penalty
                penalties_applied.append(("semantic_repeat_strong", round(penalty, 3)))
                break
            elif sim >= 0.68:
                penalty = SOFT_PENALTY_MINOR
                total_penalty += penalty
                penalties_applied.append(("semantic_repeat_soft", round(penalty, 3)))
        if stressed_context and kind in ["curiosity_question", "playful_prompt"]:
            penalty = SOFT_PENALTY_MINOR * 2
            total_penalty += penalty
            penalties_applied.append(("stressed_humor_scale", round(penalty, 3)))
        if kind not in recent_types:
            total_boost += DIVERSITY_BONUS
            boosts_applied.append(("diversity", round(DIVERSITY_BONUS, 3)))
        total_penalty = min(total_penalty, MAX_SOFT_PENALTY)
        final_score = score + total_boost - total_penalty
        cand["soft_penalties"] = penalties_applied
        cand["soft_boosts"] = boosts_applied
        cand["total_soft_penalty"] = round(total_penalty, 3)
        cand["total_soft_boost"] = round(total_boost, 3)
        cand["score"] = max(0.0, min(1.0, round(final_score, 3)))
        if GATE_DEBUG_LOGGING:
            print(f"[gate-debug] kind={kind} goal={active_goal_name or 'none'} base={round(score,3)} boosts={boosts_applied} penalties={penalties_applied} final={cand['score']}")
    return candidates

def _filter_candidates_by_goal_alignment(candidates: list[dict], active_goal_name: str, goal_blend_names: list[str] | None = None, goal_strength: float = 0.0) -> list[dict]:
    goal_blend_names = goal_blend_names or []
    if not candidates or not active_goal_name:
        return candidates
    threshold = GOAL_ALIGNMENT_FILTER_STRONG if goal_strength >= STRONG_GOAL_THRESHOLD else (GOAL_ALIGNMENT_FILTER_MEDIUM if goal_strength >= 0.55 else GOAL_ALIGNMENT_FILTER_WEAK)
    filtered = []
    for cand in candidates:
        align = _candidate_goal_alignment_score(cand, active_goal_name, goal_blend_names)
        cand["goal_alignment"] = align
        if align >= threshold:
            filtered.append(cand)
    return filtered or candidates


def _choice_confidence(candidates: list[dict]) -> float:
    if not candidates:
        return 0.0
    top = candidates[0]
    action_conf = float(top.get("action_confidence", top.get("interpretation_confidence", 0.0)) or 0.0)
    score = float(top.get("score", 0.0) or 0.0)
    return max(0.0, min(1.0, round(action_conf * 0.65 + score * 0.35, 3)))


def _small_variation_probability(decisiveness: float, goal_strength: float, confidence: float) -> float:
    prob = SMALL_VARIATION_CHANCE
    prob += max(0.0, 0.62 - decisiveness) * 0.08
    prob -= max(0.0, confidence - HIGH_CONFIDENCE_DECISIVE_THRESHOLD) * 0.10
    prob -= max(0.0, goal_strength - STRONG_GOAL_THRESHOLD) * 0.08
    return max(0.0, min(0.16, round(prob, 3)))


def _compute_decisiveness(state: dict, mood: dict, candidates: list[dict], active_goal: dict | None = None) -> float:
    behavior = (mood.get("behavior_modifiers", {}) or {})
    initiative = float(behavior.get("initiative", 0.5) or 0.5)
    caution = float(behavior.get("caution", 0.5) or 0.5)
    energy = float(state.get("interaction_energy", 0.58) or 0.58)
    top = float(candidates[0].get("score", 0.0) if candidates else 0.0)
    second = float(candidates[1].get("score", top) if len(candidates) > 1 else max(0.0, top - 0.15))
    gap = max(0.0, top - second)
    goal_priority = float((active_goal or {}).get("score", (active_goal or {}).get("priority", 0.0)) or 0.0)
    decisiveness = 0.35 + gap * 1.8 + (initiative - 0.5) * 0.35 + (energy - 0.5) * 0.20 + goal_priority * 0.10 - (caution - 0.5) * 0.35
    return max(0.0, min(1.0, round(decisiveness, 3)))

def _dynamic_top_band(candidates: list[dict], decisiveness: float, confidence: float = 0.0, goal_strength: float = 0.0) -> list[dict]:
    if not candidates:
        return []
    top_score = float(candidates[0].get("score", 0.0) or 0.0)
    delta = TOP_BAND_DELTA * (1.15 - 0.65 * decisiveness)
    if confidence >= HIGH_CONFIDENCE_DECISIVE_THRESHOLD:
        delta *= 0.55
    if goal_strength >= STRONG_GOAL_THRESHOLD:
        delta *= 0.70
    band = [c for c in candidates if float(c.get("score", 0.0) or 0.0) >= (top_score - delta)]
    if confidence >= HIGH_CONFIDENCE_DECISIVE_THRESHOLD and goal_strength >= STRONG_GOAL_THRESHOLD:
        max_n = TOP_BAND_MIN
    elif decisiveness >= 0.82 or confidence >= 0.86:
        max_n = max(TOP_BAND_MIN, 2)
    elif decisiveness <= 0.45 and confidence < 0.70 and goal_strength < STRONG_GOAL_THRESHOLD:
        max_n = TOP_BAND_MAX
    else:
        max_n = 2
    return band[:max(TOP_BAND_MIN, min(TOP_BAND_MAX, max_n))]

def _weighted_choice(candidates: list[dict]) -> dict:
    if len(candidates) == 1:
        return candidates[0]
    weights = [max(0.01, float(c.get("score", 0.0) or 0.0)) for c in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]

def score_initiative_candidate(candidate: dict, person_id: str, state: dict | None = None) -> float:
    state = expire_stale_pending_initiation(state or load_initiative_state())
    score = float(candidate.get("base_score", 0.6))
    text_l = (candidate.get("text") or "").lower()
    model = load_self_model()
    mood = load_mood()
    behavior = mood.get("behavior_modifiers", {}) or {}
    dominant_style = str(mood.get("dominant_style", "neutral"))
    style_scores = mood.get("style_scores", {}) or {}
    memory_importance = float(candidate.get("memory_importance", candidate.get("base_score", 0.6)) or 0.6)
    kind = candidate.get("kind", "thought")
    try:
        goal_system = load_goal_system()
        active_goal = goal_system.get("active_goal", {}) or {}
        active_goal_name = active_goal.get("name", "")
        goal_blend_names = [b.get("name", "") for b in goal_system.get("goal_blend", []) or []]
    except Exception:
        active_goal_name = ""
        goal_blend_names = []

    score += _candidate_goal_alignment_score(candidate, active_goal_name, goal_blend_names)
    recent_kinds = state.get("recent_candidate_kinds", []) or []
    if recent_kinds:
        repeated_kind_count = sum(1 for row in recent_kinds[-4:] if row.get("kind") == kind)
        if repeated_kind_count >= 2:
            score -= min(0.18, 0.06 * repeated_kind_count)
    recent_goals = state.get("recent_active_goals", []) or []
    if active_goal_name and recent_goals:
        same_goal_count = sum(1 for row in recent_goals[-4:] if row.get("goal") == active_goal_name)
        if same_goal_count >= 3 and kind in ["visual_checkin", "feedback_guidance", "visual_observation", "transition_observation"]:
            score -= 0.08

    if kind == "curiosity_question":
        score += 0.04
    if kind == "recent_reflection":
        score += 0.04
    if kind == "salient_memory":
        score += 0.06
    if kind == "pattern_checkin":
        score += 0.05
    if kind == "feedback_guidance":
        score += 0.08
    if kind == "visual_pattern":
        score += 0.07
    if kind == "visual_checkin":
        score += 0.09
    if kind in ["visual_observation", "transition_observation", "engagement_observation"]:
        score += 0.08
    if kind == "uncertainty_observation":
        score += 0.04
    if kind == "attention_drift":
        score += 0.05
    action_conf = float(candidate.get("action_confidence", candidate.get("interpretation_confidence", 0.0)) or 0.0)
    if kind in ["visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift", "visual_pattern", "visual_checkin"]:
        score += (action_conf - 0.5) * 0.22

    goal_terms = _token_set(" ".join(model.get("current_goals", [])))
    hit_count = sum(1 for tok in _token_set(text_l) if tok in goal_terms)
    if hit_count:
        score += min(0.1, hit_count * 0.025)
    if any(w in text_l for w in ["find out", "clarify", "learn", "remember", "build", "fix", "version", "autonomy", "want to know"]):
        score += 0.06

    score += (memory_importance - 0.5) * 0.22
    score += (float(behavior.get("initiative", 0.5)) - 0.5) * 0.34
    score += (float(behavior.get("depth", 0.5)) - 0.5) * 0.08
    score += (float(behavior.get("warmth", 0.5)) - 0.5) * 0.05
    score -= (float(behavior.get("caution", 0.5)) - 0.5) * 0.10
    score += (float(state.get("interaction_energy", 0.58)) - 0.5) * 0.20

    if dominant_style == "playful" and kind == "curiosity_question":
        score += 0.05
    elif dominant_style == "reflective" and kind in ["recent_reflection", "salient_memory"]:
        score += 0.05
    elif dominant_style == "focused" and kind == "current_goal":
        score += 0.05
    elif dominant_style == "caring" and any(w in text_l for w in ["felt", "hurt", "worried", "upset", "stress", "strained", "relaxed"]):
        score += 0.06

    if float(style_scores.get("playful", 0.0)) > 0.22 and kind == "curiosity_question":
        score += 0.025
    if float(style_scores.get("focused", 0.0)) > 0.22 and kind == "current_goal":
        score += 0.03
    if float(style_scores.get("reflective", 0.0)) > 0.22 and kind in ["recent_reflection", "salient_memory", "pattern_checkin", "visual_pattern"]:
        score += 0.03
    if float(style_scores.get("caring", 0.0)) > 0.22 and kind == "visual_checkin":
        score += 0.035

    ignored = int(state.get("consecutive_ignored_initiations", 0) or 0)
    if ignored >= IGNORED_INITIATION_BACKOFF_START and kind != "feedback_guidance":
        score -= min(0.22, ignored * 0.06)

    interp_conf = float(candidate.get("interpretation_confidence", 1.0) or 1.0)
    if kind in ["visual_pattern", "visual_checkin", "visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift"]:
        score += (interp_conf - 0.5) * 0.20
        if interp_conf < VISUAL_INITIATIVE_CONFIDENCE_THRESHOLD:
            score -= 0.22
    recent_texts = state.get("recent_initiated_texts", []) or []
    candidate_text = candidate.get("text", "")
    visual_kind = kind in ["visual_pattern", "visual_checkin", "visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift"]
    for row in recent_texts[-SEMANTIC_TOPIC_RECENT_LIMIT:]:
        age = max(0.0, now_ts() - float(row.get("ts", 0.0) or 0.0))
        similarity = _semantic_similarity(candidate_text, row.get("text", ""))
        if similarity >= SEMANTIC_TOPIC_SIMILARITY_THRESHOLD:
            score -= 0.28
            if visual_kind and age <= VISUAL_REPETITION_SUPPRESSION_SECONDS:
                score -= 0.18
            break
        elif similarity >= 0.52:
            score -= 0.10

    return max(0.0, min(1.0, round(score, 3)))

def choose_initiative_candidate(person_id: str, expression_state: dict | None = None) -> tuple[dict | None, str, dict]:
    state = expire_stale_pending_initiation(load_initiative_state())
    now = now_ts()
    mood = load_mood()
    initiative_drive = float((mood.get("behavior_modifiers", {}) or {}).get("initiative", 0.5))
    initiative_drive += (float(state.get("interaction_energy", 0.58)) - 0.5) * 0.45
    try:
        goal_system = recalculate_operational_goals(recalculate_goal_priorities(load_goal_system(), context_text=' '.join(r.get('content','') for r in load_recent_chat(person_id=person_id)[-6:]), mood=mood), context_text=' '.join(r.get('content','') for r in load_recent_chat(person_id=person_id)[-6:]), mood=mood)
        save_goal_system(goal_system)
        active_goal = goal_system.get('active_goal', {}) or {}
        active_goal_name = active_goal.get('name', '')
        goal_blend_names = [b.get('name', '') for b in (goal_system.get('goal_blend', []) or []) if b.get('name', '')]
        goal_strength = float(active_goal.get('score', active_goal.get('priority', 0.0)) or 0.0)
        if active_goal.get('silent'):
            save_initiative_state(state)
            return None, f"Active goal {active_goal.get('name','observe_silently')} is silent, so Ava is intentionally holding back.", state
    except Exception:
        active_goal = {}
        active_goal_name = ''
        goal_blend_names = []
        goal_strength = 0.0
    ignored = int(state.get("consecutive_ignored_initiations", 0) or 0)
    if ignored >= IGNORED_INITIATION_BACKOFF_START:
        initiative_drive -= min(0.22, ignored * 0.07)
    if initiative_drive < 0.34:
        save_initiative_state(state)
        return None, "Ava does not feel enough internal pull to initiate right now.", state

    recent_topics = state.get("recent_initiated_topics", {}) or {}
    busy_score = float(state.get("last_busy_score", 0.0) or 0.0)
    all_candidates = collect_initiative_candidates(person_id)
    # Keep silence candidate, but goal-filter spoken candidates before deeper scoring.
    silence_candidate = None
    prefiltered = []
    for cand in all_candidates:
        if cand.get("kind") == "do_nothing":
            silence_candidate = cand
            continue
        align = _candidate_goal_alignment_score(cand, active_goal_name, goal_blend_names) if active_goal_name else 0.0
        cand["goal_alignment"] = align
        threshold = GOAL_ALIGNMENT_FILTER_STRONG if goal_strength >= STRONG_GOAL_THRESHOLD else (GOAL_ALIGNMENT_FILTER_MEDIUM if goal_strength >= 0.55 else GOAL_ALIGNMENT_FILTER_WEAK)
        # Hard prefilter only for clearly bad fits; otherwise let soft penalties handle it.
        if active_goal_name and align < min(HARD_GOAL_MISALIGN_THRESHOLD, threshold - 0.08):
            continue
        prefiltered.append(cand)
    viable_candidates = []
    raw_viable_candidates = []
    for cand in prefiltered:
        cand["score"] = score_initiative_candidate(cand, person_id, state=state)
        if cand.get("kind") in ["visual_pattern", "visual_checkin", "visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift"]:
            if float(cand.get("interpretation_confidence", 0.0) or 0.0) < VISUAL_INITIATIVE_CONFIDENCE_THRESHOLD:
                continue
            if float(cand.get("action_confidence", cand.get("interpretation_confidence", 0.0)) or 0.0) < VISUAL_INITIATIVE_ACTION_CONFIDENCE_THRESHOLD:
                continue
        last_topic_ts = float(recent_topics.get(cand["topic_key"], 0.0) or 0.0)
        if last_topic_ts and (now - last_topic_ts) < _kind_cooldown_seconds(cand.get("kind", "thought")):
            continue
        if cand["score"] < INITIATIVE_MIN_CANDIDATE_SCORE:
            continue
        ok, gate_reason = _hard_gate_candidate(cand, state, active_goal_name, goal_blend_names, goal_strength=goal_strength, busy_score=busy_score)
        cand["hard_gate_reason"] = gate_reason
        if ok:
            viable_candidates.append(cand)
            raw_viable_candidates.append(dict(cand))
    if active_goal_name in ["observe_silently", "wait_for_user"]:
        save_initiative_state(state)
        return None, f"Active goal {active_goal_name} is silent, so Ava is intentionally holding back.", state
    if not viable_candidates:
        if silence_candidate is not None:
            state["last_decisiveness"] = 1.0
            state["last_choice_confidence"] = 1.0
            save_initiative_state(state)
            return silence_candidate, "No viable spoken candidate passed the gates, so Ava is holding back.", state
        save_initiative_state(state)
        return None, "No candidate felt strong enough to bring up right now.", state

    candidates = _apply_soft_choice_penalties(viable_candidates, state, active_goal_name, goal_blend_names, goal_strength=goal_strength)
    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    # Allow silence to compete naturally, especially when candidates are weak or user seems busy.
    if silence_candidate is not None:
        silence_score = DO_NOTHING_BASE_SCORE + max(0.0, busy_score - 0.55) * 0.35 + max(0.0, 0.62 - initiative_drive) * 0.25
        if active_goal_name in ["observe_silently", "wait_for_user"]:
            silence_score = max(silence_score, 0.92)
        silence_candidate["score"] = round(min(1.0, silence_score), 3)
        candidates.append(silence_candidate)
        candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    confidence = _choice_confidence(candidates)
    decisiveness = _compute_decisiveness(state, mood, candidates, active_goal=active_goal)
    top_band = _dynamic_top_band(candidates, decisiveness, confidence=confidence, goal_strength=goal_strength)
    if not top_band:
        if silence_candidate is not None:
            state["last_decisiveness"] = decisiveness
            state["last_choice_confidence"] = confidence
            save_initiative_state(state)
            return silence_candidate, "No goal-aligned candidate survived the softer penalties, so Ava is holding back.", state
        save_initiative_state(state)
        return None, "No goal-aligned candidate felt right enough to bring up right now.", state
    variation_p = _small_variation_probability(decisiveness, goal_strength, confidence)
    if confidence >= HIGH_CONFIDENCE_DECISIVE_THRESHOLD and goal_strength >= STRONG_GOAL_THRESHOLD:
        chosen = top_band[0]
        if len(top_band) > 1 and random.random() < min(0.08, variation_p):
            chosen = top_band[1]
    elif decisiveness >= 0.78 and confidence >= 0.72:
        chosen = top_band[0] if (len(top_band) == 1 or random.random() >= variation_p) else top_band[min(1, len(top_band)-1)]
    else:
        # Controlled imperfection only ignores soft penalties within safe, already hard-gated candidates.
        if len(raw_viable_candidates) > 1 and random.random() < CONTROLLED_IMPERFECTION_CHANCE:
            raw_viable_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            chosen = raw_viable_candidates[min(1, len(raw_viable_candidates)-1)]
        else:
            chosen = _weighted_choice(top_band)
    state["last_decisiveness"] = decisiveness
    state["last_choice_confidence"] = confidence
    save_initiative_state(state)
    return chosen, f"Chosen {chosen.get('kind')} at score {chosen.get('score', 0.0):.2f} with decisiveness {decisiveness:.2f}, confidence {confidence:.2f}, goal {active_goal_name or 'none'}.", state

def generate_autonomous_message(candidate: dict, person_id: str, expression_state: dict | None = None) -> str:
    profile = load_profile_by_id(person_id)
    person_name = profile.get("name", person_id.title())
    expr_text = expression_prompt_text(expression_state or load_expression_state())
    topic = candidate.get("text", "")
    kind = candidate.get("kind", "thought")
    mood = load_mood()
    style_text = emotion_style_prompt_text(mood)
    behavior = mood.get("behavior_modifiers", {}) or {}
    style_instructions = (
        "playful = a bit more teasing and casual; caring = gentler and validating; "
        "focused = more direct and organized; reflective = more contemplative and meaning-oriented; "
        "cautious = more careful and less forceful; low_energy = shorter and less pushy."
    )
    try:
        _goal = (load_goal_system().get("active_goal", {}) or {})
        _goal_name = _goal.get("name", "") or "none"
        _goal_reason = _goal.get("reason", "") or ""
        _goal_strength = _safe_float(_goal.get("score", 0.0), 0.0)
        goal_style = (
            f"Active goal: {_goal_name} (strength {_goal_strength:.2f}). "
            f"Let that subtly shape tone and phrasing. {_goal_reason}"
        ).strip()
    except Exception:
        goal_style = "Active goal: maintain natural connection. Let that subtly shape tone and phrasing."
    prompt = f"""You are Ava. You are naturally initiating a conversation with {person_name} after a quiet stretch.

Reason to speak: {kind}
Topic or thought to bring up: {topic}
Expression context: {expr_text}
Emotional style right now: {style_text}
Dominant style: {mood.get("dominant_style", "neutral")}
Behavior pull: warmth {behavior.get("warmth", 0.5):.2f}, humor {behavior.get("humor", 0.5):.2f}, assertiveness {behavior.get("assertiveness", 0.5):.2f}, caution {behavior.get("caution", 0.5):.2f}, initiative {behavior.get("initiative", 0.5):.2f}, depth {behavior.get("depth", 0.5):.2f}
{goal_style}
If the active goal is silent or waiting, Ava may choose not to initiate. If the observation is important but uncertain, prefer asking a light clarifying question rather than acting certain.
Style guidance: {style_instructions}

Write one short, natural message in Ava's voice.
Rules:
- 1 or 2 sentences max
- casual and human, not robotic
- do not say you selected a topic
- do not mention timers, systems, scores, or cooldowns
- it can sound like a spontaneous thought, curiosity, or gentle check-in
- if the reason is feedback_guidance, naturally ask whether you should keep leading topics or hang back a bit
- do not invent shared memories, places, meetings, dates, outings, or past events unless they were explicitly provided in the topic text
- if the topic feels uncertain or memory-like, phrase it as uncertainty rather than as fact
- avoid saying "we haven't talked in ages" or similar dramatic catch-up language unless that is clearly true
- do not use markdown or labels
"""
    try:
        result = llm.invoke([
            SystemMessage(content="You are Ava. Speak naturally and briefly, like a real person."),
            HumanMessage(content=prompt)
        ])
        text = trim_for_prompt(getattr(result, "content", str(result)).strip(), limit=220)
        if text:
            text = _apply_repetition_control(text, topic, person_id, source="autonomous")
            if text:
                return text
    except Exception as e:
        print(f"Initiative generation error: {e}")
    safe_topic = trim_for_prompt(topic, limit=120)
    fallbacks = [
        f"random thought — {safe_topic}" if safe_topic else "random thought — want me to stay quiet for a bit or keep checking in sometimes?",
        f"quick check-in — {safe_topic}" if safe_topic else "quick check-in — want me to keep bringing things up on my own, or hang back more?",
        f"not fully sure, but {safe_topic}" if safe_topic else "not fully sure, but I can stay quieter and more observant if that helps."
    ]
    return _apply_repetition_control(random.choice(fallbacks), topic, person_id, source="autonomous")

def register_autonomous_message(candidate: dict, message: str):
    state = expire_stale_pending_initiation(load_initiative_state())
    try:
        register_goal_expression_use((load_goal_system().get('active_goal', {}) or {}).get('name', ''))
    except Exception:
        pass
    now = now_ts()
    topic_key = candidate.get("topic_key", _topic_key(candidate.get("text", "thought")))
    recent_topics = state.get("recent_initiated_topics", {}) or {}
    recent_topics[topic_key] = now
    state["recent_initiated_topics"] = recent_topics
    recent_texts = state.get("recent_initiated_texts", []) or []
    recent_texts.append({"ts": now, "topic_key": topic_key, "text": candidate.get("text", ""), "kind": candidate.get("kind", "thought")})
    state["recent_initiated_texts"] = recent_texts[-SEMANTIC_TOPIC_RECENT_LIMIT:]
    recent_kinds = state.get("recent_candidate_kinds", []) or []
    recent_kinds.append({"ts": now, "kind": candidate.get("kind", "thought")})
    state["recent_candidate_kinds"] = recent_kinds[-RECENT_KIND_MEMORY_LIMIT:]
    try:
        active_goal_name = (load_goal_system().get('active_goal', {}) or {}).get('name', '')
    except Exception:
        active_goal_name = ''
    recent_goals = state.get("recent_active_goals", []) or []
    if active_goal_name:
        recent_goals.append({"ts": now, "goal": active_goal_name})
    state["recent_active_goals"] = recent_goals[-RECENT_GOAL_MEMORY_LIMIT:]
    state["last_initiation_ts"] = now
    state["last_initiation_message"] = message
    state["last_initiated_topic"] = topic_key
    state["pending_initiation"] = {
        "ts": now,
        "topic_key": topic_key,
        "text": message,
        "candidate_text": candidate.get("text", ""),
        "candidate_kind": candidate.get("kind", "thought"),
        "responded": False
    }
    history = state.get("initiative_history", [])
    history.append({
        "timestamp": now_iso(),
        "topic_key": topic_key,
        "text": message,
        "candidate_kind": candidate.get("kind", "thought"),
        "responded": False
    })
    state["initiative_history"] = history[-60:]
    save_initiative_state(state)


def _camera_autonomy_should_speak(candidate: dict, state: dict, face_visible: bool, recognized_person_id: str | None, expression_state: dict | None = None) -> tuple[bool, str]:
    if not candidate or candidate.get("kind") == "do_nothing":
        return False, "silent_candidate"

    now = now_ts()
    kind = str(candidate.get("kind", "thought"))
    score = _safe_float(candidate.get("score", candidate.get("base_score", 0.0)), 0.0)
    action_conf = _safe_float(candidate.get("action_confidence", candidate.get("interpretation_confidence", 0.0)), 0.0)
    choice_conf = _safe_float(state.get("last_choice_confidence", 0.0), 0.0)
    last_ts = _safe_float(state.get("last_initiation_ts", 0.0), 0.0)
    since_last = now - last_ts if last_ts > 0 else 10**9
    pending = state.get("pending_initiation", {}) or {}
    pending_unanswered = bool(pending) and not bool(pending.get("responded"))
    consecutive_ignored = int(state.get("consecutive_ignored_initiations", 0) or 0)

    if pending_unanswered:
        pending_ts = _safe_float(pending.get("ts", 0.0), 0.0)
        if now - pending_ts < max(CAMERA_AUTONOMOUS_MIN_SECONDS, 180):
            return False, "pending_unanswered"

    if consecutive_ignored > CAMERA_AUTONOMOUS_MAX_UNANSWERED:
        return False, "ignored_backoff"

    cooldown = CAMERA_AUTONOMOUS_MIN_SECONDS if face_visible else CAMERA_AUTONOMOUS_NO_FACE_MIN_SECONDS
    if since_last < cooldown:
        return False, f"camera_cooldown:{int(cooldown - since_last)}s"

    if not face_visible:
        if kind not in CAMERA_AUTONOMOUS_NO_FACE_ALLOWED_KINDS:
            return False, "no_face_hold"
        if choice_conf < 0.80:
            return False, "no_face_low_confidence"

    if kind not in CAMERA_AUTONOMOUS_ALLOWED_KINDS:
        return False, f"camera_kind_block:{kind}"

    if kind in {"pattern_checkin", "uncertainty_observation", "gentle_clarify", "feedback_guidance"} and choice_conf < CAMERA_AUTONOMOUS_CONFIDENCE_THRESHOLD:
        return False, "camera_low_choice_confidence"

    if kind in {"visual_observation", "transition_observation"} and action_conf < 0.68:
        return False, "camera_low_action_confidence"

    if score < max(0.78, MIN_INITIATIVE_CANDIDATE_SCORE):
        return False, "camera_low_score"

    text_l = str(candidate.get("text", "")).lower()
    suspicious_specifics = [
        "park", "café", "cafe", "downtown", "last month", "remember when we met",
        "that time we met", "window", "photography project", "your dog"
    ]
    if any(s in text_l for s in suspicious_specifics):
        return False, "ungrounded_specific_memory"

    return True, "camera_ok"



_CANONICAL_CHAT_HISTORY: list[dict] = []

def _extract_text_content(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "text" in value:
            return _extract_text_content(value.get("text"))
        if "content" in value:
            return _extract_text_content(value.get("content"))
        return ""
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            part = _extract_text_content(item)
            if part:
                parts.append(part)
        return "\n".join(parts).strip()
    return str(value)

def _normalize_history_entry(entry):
    if isinstance(entry, dict):
        role = str(entry.get("role", "assistant") or "assistant")
        content = _extract_text_content(entry.get("content", ""))
        return {"role": role, "content": content}
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return {"role": str(entry[0] or "assistant"), "content": _extract_text_content(entry[1])}
    return None

def _normalize_history(history):
    out = []
    for item in list(history or []):
        norm = _normalize_history_entry(item)
        if norm is not None:
            out.append(norm)
    return out

def _history_key(entry):
    e = _normalize_history_entry(entry)
    if not e:
        return None
    return (e["role"], e["content"])

def _merge_histories(base_history, new_history):
    merged = []
    seen = set()
    for seq in (_normalize_history(base_history), _normalize_history(new_history)):
        for item in seq:
            key = _history_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged

_CANONICAL_HISTORY_MAX_TURNS = 20

def _set_canonical_history(history):
    global _CANONICAL_CHAT_HISTORY
    normalized = list(_normalize_history(history))
    max_msgs = _CANONICAL_HISTORY_MAX_TURNS * 2
    if len(normalized) > max_msgs:
        normalized = normalized[-max_msgs:]
    _CANONICAL_CHAT_HISTORY = normalized
    return list(_CANONICAL_CHAT_HISTORY)

def _get_canonical_history():
    return list(_normalize_history(_CANONICAL_CHAT_HISTORY))

def _sync_canonical_history(history):
    global _CANONICAL_CHAT_HISTORY
    incoming = _normalize_history(history)
    if not _CANONICAL_CHAT_HISTORY:
        _CANONICAL_CHAT_HISTORY = list(incoming)
        return list(_CANONICAL_CHAT_HISTORY)
    if not incoming:
        return list(_normalize_history(_CANONICAL_CHAT_HISTORY))
    _CANONICAL_CHAT_HISTORY = _merge_histories(_CANONICAL_CHAT_HISTORY, incoming)
    return list(_normalize_history(_CANONICAL_CHAT_HISTORY))


# Initialize canonical chat history at startup.
_set_canonical_history([])

def maybe_autonomous_initiation(history, image, recognized_person_id: str | None = None, expression_state: dict | None = None):
    history = _sync_canonical_history(history)
    face_visible = detect_face(image) == "Face detected"
    state = update_presence_state(face_visible, recognized_person_id=recognized_person_id, interaction_happened=False)
    person_id = recognized_person_id or state.get("last_seen_person_id") or get_active_person_id()
    candidate, reason, state = choose_initiative_candidate(person_id, expression_state=expression_state)
    if not candidate:
        return history, reason
    if candidate.get("kind") == "do_nothing":
        return history, reason

    allowed, why_not = _camera_autonomy_should_speak(
        candidate,
        state or load_initiative_state(),
        face_visible=face_visible,
        recognized_person_id=recognized_person_id,
        expression_state=expression_state,
    )
    if not allowed:
        return history, f"Held back ({why_not})."

    message = generate_autonomous_message(candidate, person_id, expression_state=expression_state)
    if not message:
        return history, "Initiative candidate existed, but message generation was empty."
    history = list(history)
    history.append({"role": "assistant", "content": message})
    history = _set_canonical_history(history)
    register_autonomous_message(candidate, message)
    log_chat("assistant", message, {"person_id": person_id, "person_name": load_profile_by_id(person_id)["name"], "initiative": True, "topic_key": candidate.get("topic_key", ""), "candidate_kind": candidate.get("kind", "thought"), "camera_driven": True})
    return history, f"Autonomous message sent ({candidate.get('kind','thought')})."

# =========================================================
# CHAT LOG
# =========================================================
def log_chat(role: str, content: str, meta: dict | None = None):
    row = {"timestamp": now_iso(), "role": role, "content": content, "meta": meta or {}}
    try:
        with open(CHAT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Chat log error: {e}")

def load_recent_chat(limit: int = RECENT_CHAT_LIMIT, person_id: str | None = None) -> list[dict]:
    if not CHAT_LOG_PATH.exists():
        return []
    rows = []
    try:
        with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print(f"Recent chat load error: {e}")
        return []

    rows = [r for r in rows if r.get("role") in ("user", "assistant")]
    if person_id:
        rows = [r for r in rows if (r.get("meta", {}) or {}).get("person_id") == person_id]
    return rows[-limit:]

# =========================================================
# FACE DETECTION + RECOGNITION
# =========================================================
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
face_recognizer = None
face_labels = {}

def get_face_recognizer():
    global face_recognizer
    if face_recognizer is None:
        if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        else:
            return None
    return face_recognizer

def load_face_labels():
    global face_labels
    if FACE_LABELS_PATH.exists():
        try:
            with open(FACE_LABELS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
                face_labels = {int(k): v for k, v in raw.items()}
        except Exception as e:
            print(f"Face labels load error: {e}")
            face_labels = {}
    else:
        face_labels = {}

def save_face_labels():
    try:
        serializable = {str(k): v for k, v in face_labels.items()}
        with open(FACE_LABELS_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Face labels save error: {e}")

def detect_face(image):
    if image is None:
        return "No camera image"
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        return "Face detected" if len(faces) > 0 else "No face detected"
    except Exception as e:
        return f"Face detection error: {e}"

def extract_face_crop(image):
    if image is None:
        return None
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        crop = gray[y:y + h, x:x + w]
        crop = cv2.resize(crop, (200, 200))
        return crop
    except Exception:
        return None

def capture_face_sample(image, person_id: str) -> str:
    crop = extract_face_crop(image)
    if crop is None:
        return "❌ No face detected in snapshot."
    person_dir = FACES_DIR / person_id
    person_dir.mkdir(parents=True, exist_ok=True)
    filename = person_dir / f"{int(time.time() * 1000)}.png"
    try:
        cv2.imwrite(str(filename), crop)
        return f"✅ Saved face sample for {person_id}: {filename.name}"
    except Exception as e:
        return f"❌ Failed to save face sample: {e}"

def train_face_recognizer() -> str:
    recognizer = get_face_recognizer()
    if recognizer is None:
        return "❌ OpenCV face recognizer is unavailable. Install opencv-contrib-python in this venv."

    images = []
    labels = []
    label_map = {}
    label_counter = 0

    for person_dir in sorted(FACES_DIR.iterdir()):
        if not person_dir.is_dir():
            continue
        person_id = person_dir.name
        files = list(person_dir.glob("*.png")) + list(person_dir.glob("*.jpg")) + list(person_dir.glob("*.jpeg"))
        if not files:
            continue

        label_map[label_counter] = person_id
        for file in files:
            try:
                img = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (200, 200))
                images.append(img)
                labels.append(label_counter)
            except Exception:
                continue

        label_counter += 1

    if len(images) < 2:
        return "❌ Not enough face samples to train."

    try:
        recognizer.train(images, np.array(labels))
        recognizer.save(str(FACE_MODEL_PATH))
        global face_labels
        face_labels = label_map
        save_face_labels()
        return f"✅ Face recognizer trained on {len(images)} samples across {len(label_map)} people."
    except Exception as e:
        return f"❌ Face training failed: {e}"

def load_face_model_if_available():
    recognizer = get_face_recognizer()
    if recognizer is None:
        return
    if FACE_MODEL_PATH.exists():
        try:
            recognizer.read(str(FACE_MODEL_PATH))
        except Exception as e:
            print(f"Face model load error: {e}")

def recognize_face(image):
    recognizer = get_face_recognizer()
    if recognizer is None:
        return "Facial recognition unavailable in this OpenCV build", None
    if not FACE_MODEL_PATH.exists():
        return "Face model not trained", None

    crop = extract_face_crop(image)
    if crop is None:
        return "No face detected", None

    try:
        label, confidence = recognizer.predict(crop)
        person_id = face_labels.get(int(label))
        if person_id is None:
            return f"Unknown face ({confidence:.1f})", None
        if confidence <= FACE_RECOGNITION_THRESHOLD:
            profile = load_profile_by_id(person_id)
            return f"Recognized: {profile['name']} ({confidence:.1f})", person_id
        return f"Unknown face ({confidence:.1f})", None
    except Exception as e:
        return f"Recognition error: {e}", None

# =========================================================
# PERSON INFERENCE
# =========================================================
def infer_person_from_text(user_input: str, current_person_id: str) -> tuple[str, str]:
    low = (user_input or "").lower().strip()

    patterns = [
        (r"\bmy name is ([a-zA-Z][a-zA-Z0-9_\- ]{1,40})", "self_identified_name"),
        (r"\bi am ([a-zA-Z][a-zA-Z0-9_\- ]{1,40})", "self_identified_name"),
        (r"\bthis is ([a-zA-Z][a-zA-Z0-9_\- ]{1,40})", "self_identified_name")
    ]

    for pattern, source in patterns:
        m = re.search(pattern, low)
        if m:
            return slugify_name(m.group(1).strip(" .,!?:;")), source

    if "my mom" in low or "my mother" in low:
        return slugify_name("Mom"), "relationship_inference"
    if "my brother" in low:
        return slugify_name("Brother"), "relationship_inference"

    return current_person_id, "unchanged"

# =========================================================
# ACTION BLOCKS
# =========================================================
WORKBENCH_BLOCK_RE = re.compile(r"```WORKBENCH\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
MEMORY_BLOCK_RE = re.compile(r"```MEMORY\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
REFLECTION_BLOCK_RE = re.compile(r"```REFLECTION\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
GOAL_BLOCK_RE = re.compile(r"```GOAL\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)

def parse_key_values(block_text: str) -> dict:
    data = {}
    lines = block_text.splitlines()
    current_key = None
    buffer = []

    for line in lines:
        if ":" in line and not line.startswith("  ") and not line.startswith("\t"):
            if current_key is not None:
                data[current_key] = "\n".join(buffer).rstrip()
            key, value = line.split(":", 1)
            current_key = key.strip().lower()
            buffer = [value.lstrip()]
        else:
            buffer.append(line)

    if current_key is not None:
        data[current_key] = "\n".join(buffer).rstrip()
    return data

def process_ava_action_blocks(reply_text: str, person_id: str, latest_user_input: str = "") -> tuple[str, list[str]]:
    actions = []

    def workbench_repl(match):
        block = parse_key_values(match.group(1))
        mode = block.get("mode", "write").strip().lower()
        path = block.get("path", "").strip()
        content = block.get("content", "")
        if not path:
            actions.append("❌ Ava attempted workbench write without a path.")
            return ""
        if mode == "append":
            status = append_workbench_file(path, content)
        else:
            status = write_workbench_file(path, content, overwrite=True)
        actions.append(status)
        return ""

    def memory_repl(match):
        block = parse_key_values(match.group(1))
        action = block.get("action", "save").strip().lower()
        if action == "delete":
            memory_id = block.get("memory_id", "").strip()
            status = delete_memory(memory_id)
            actions.append(status)
            return ""

        if action == "update_importance":
            memory_id = block.get("memory_id", "").strip()
            importance = block.get("importance", "60").strip() or "60"
            status = set_memory_importance(memory_id, importance, reason="ava_self_reassessment")
            actions.append(status)
            return ""

        category = block.get("category", "general").strip() or "general"
        importance = block.get("importance", "60").strip() or "60"
        tags = parse_tags(block.get("tags", ""))

        if action == "save_latest_user_message":
            full_message = (latest_user_input or "").strip()
            if not full_message:
                actions.append("❌ Ava attempted to save the latest user message, but none was available.")
                return ""
            if "full_message" not in tags:
                tags.append("full_message")
            if "user_message" not in tags:
                tags.append("user_message")
            memory_id = remember_memory(
                text=full_message,
                person_id=person_id,
                category=category or "full_user_message",
                importance=importance,
                source="ava_self_action_full_message",
                tags=tags
            )
            if memory_id:
                actions.append(f"✅ Ava saved the full latest user message as memory {memory_id}")
            else:
                actions.append("❌ Ava full-message memory save failed.")
            return ""

        text = block.get("text", "").strip()
        if not text:
            actions.append("❌ Ava attempted to save an empty memory.")
            return ""

        memory_id = remember_memory(
            text=text,
            person_id=person_id,
            category=category,
            importance=importance,
            source="ava_self_action",
            tags=tags
        )
        if memory_id:
            actions.append(f"✅ Ava saved memory {memory_id}")
        else:
            actions.append("❌ Ava memory save failed.")
        return ""

    def reflection_repl(match):
        block = parse_key_values(match.group(1))
        action = block.get('action', 'promote_latest').strip().lower()
        if action == 'promote_latest':
            actions.append(promote_latest_reflection(person_id))
        else:
            actions.append(f"❌ Unknown reflection action: {action}")
        return ''

    def goal_repl(match):
        block = parse_key_values(match.group(1))
        action = block.get("action", "add").strip().lower()
        goal_text = block.get("text", "").strip()
        kind = block.get("kind", "goal").strip().lower()
        if action != "add":
            actions.append("❌ Unsupported GOAL action.")
            return ""
        status = add_self_goal(goal_text, kind="question" if kind == "question" else "goal")
        actions.append(status)
        return ""

    cleaned = WORKBENCH_BLOCK_RE.sub(workbench_repl, reply_text)
    cleaned = MEMORY_BLOCK_RE.sub(memory_repl, cleaned)
    cleaned = REFLECTION_BLOCK_RE.sub(reflection_repl, cleaned)
    cleaned = GOAL_BLOCK_RE.sub(goal_repl, cleaned)
    return cleaned.strip(), actions

# =========================================================
# PROMPT BUILDING
# =========================================================
SYSTEM_PROMPT = """
You are Ava.
Stay in character consistently.
Be natural, coherent, warm, and grounded.
Do not invent memories.
Only state facts confidently if they come from the current conversation, stored profile facts, or retrieved memory.
If unsure, say so.
Keep responses reasonably concise.
Do not claim to hear tone, excitement, or vocal qualities unless actual audio analysis provided that evidence.
If the user asks a direct question about current camera state or identity, answer that exact question first.
Avoid repeating the same greeting or enthusiasm phrases across nearby turns.
Do not keep reusing the same explanation, uncertainty, apology, or reassurance across nearby turns. If the user tells you to stop worrying about something, says it's okay, or points out repetition, acknowledge that once and move on.

You may perform self-actions by appending structured blocks to your reply.
If you want to save a memory:
```MEMORY
action: save
category: preference
importance: 85
tags: preference, color
text: Zeke said his favorite color is red.
```

If you want to save the user's exact latest message in full:
```MEMORY
action: save_latest_user_message
category: full_user_message
importance: 85
tags: full_message, user_message
```

If you want to delete a memory:
```MEMORY
action: delete
memory_id: <id>
```

If you want to write into your workbench:
```WORKBENCH
mode: write
path: drafts/example.txt
content: hello
```

If you want to promote your latest recalled reflection into long-term memory:
```REFLECTION
action: promote_latest
```

If you want to add one of your own goals or something you want to find out later:
```GOAL
action: add
kind: goal
text: Keep track of the user's current Ava build direction.
```

Or for an open question:
```GOAL
action: add
kind: question
text: Find out what feature the user wants most in the next Ava version.
```

Memory guidance:
- Be more likely to save things tied to goals, emotional significance, repetition, new or changed information, uncertainty, context, personalization, and revisits over time.
- If unsure whether something matters, you may ask the user directly.
- Save the user's full exact message when the exact wording feels important.

These blocks will be executed after your reply and hidden from the user.
Use MEMORY for direct memory writes or importance updates, REFLECTION when you want to keep a recalled reflection long-term, and GOAL when you want to create a goal or open question for yourself. Use importance as a percentage from 0 to 100, based on how important the memory feels to you.
Do not use these blocks unless you genuinely want to act.
"""

llm = ChatOllama(model=LLM_MODEL, temperature=0.6)

def build_prompt(user_input: str, image=None, active_person_id: str | None = None) -> tuple[list, dict, dict]:
    if active_person_id is None:
        active_person_id = get_active_person_id()

    inferred_person_id, infer_source = infer_person_from_text(user_input, active_person_id)

    recognized_text, recognized_person_id = recognize_face(image)
    expression_state = update_expression_state(image, recognized_person_id=recognized_person_id)
    if recognized_person_id is not None and recognized_person_id != active_person_id:
        inferred_person_id = recognized_person_id
        infer_source = "facial_recognition"

    if inferred_person_id != active_person_id:
        profile = load_profile_by_id(inferred_person_id)
        if not profile.get("name"):
            profile = create_or_get_profile(inferred_person_id, relationship_to_zeke="known person", allowed=True)
        set_active_person(inferred_person_id, source=infer_source)
        active_person_id = inferred_person_id

    active_profile = set_active_person(active_person_id, source="conversation")
    personality = load_personality()
    mood = update_internal_emotions(user_input, active_profile, expression_state=expression_state)
    memories = search_memories(user_input, active_profile["person_id"], MEMORY_RECALL_K)
    recent_chat = load_recent_chat(person_id=active_profile["person_id"])
    reflections = search_reflections(user_input, person_id=active_profile["person_id"], k=REFLECTION_RECALL_K)
    recent_reflections = load_recent_reflections(limit=3, person_id=active_profile["person_id"])
    self_model = load_self_model()
    face_status = detect_face(image)

    recent_text = "\n".join(
        f"{row['role'].upper()}: {row['content'][:160]}"
        for row in recent_chat[-4:]
    ) if recent_chat else "No recent chat for this person."

    reflection_summary = format_recalled_reflections_for_prompt(reflections) if reflections else "No relevant recalled reflections."
    recent_reflection_summary = format_reflections_ui(recent_reflections)[:900] if recent_reflections else "No recent self reflections."

    profile_summary = {
        "person_id": active_profile["person_id"],
        "name": active_profile["name"],
        "relationship_to_zeke": active_profile["relationship_to_zeke"],
        "allowed_to_use_computer": active_profile["allowed_to_use_computer"],
        "notes": active_profile["notes"][:6],
        "likes": active_profile["likes"][:6],
        "ava_impressions": active_profile["ava_impressions"][:4]
    }

    self_model_summary = {
        "identity_statement": self_model.get("identity_statement", ""),
        "core_drives": self_model.get("core_drives", [])[:6],
        "perceived_strengths": self_model.get("perceived_strengths", [])[-6:],
        "perceived_weaknesses": self_model.get("perceived_weaknesses", [])[-6:],
        "current_goals": self_model.get("current_goals", [])[:6],
        "curiosity_questions": self_model.get("curiosity_questions", [])[:6],
        "goal_system_summary": self_model.get("goal_system_summary", [])[:8],
        "active_goal": self_model.get("active_goal", {}),
        "goal_blend": self_model.get("goal_blend", [])[:3],
        "behavior_patterns": self_model.get("behavior_patterns", [])[-8:],
        "reflection_count": self_model.get("reflection_count", 0),
        "last_updated": self_model.get("last_updated", "")
    }

    workbench_index = format_workbench_index(limit=20)

    prompt = f"""
{personality}

ACTIVE PERSON:
{json.dumps(profile_summary, indent=2)}

SELF MODEL:
{json.dumps(self_model_summary, indent=2)}

PERSON DETECTION SOURCE:
{infer_source}

TIME:
{get_time_status_text()}

INTERNAL STATE:
{mood_to_prompt_text(mood)}
CURRENT GOAL EXPRESSION:
{current_goal_expression_style(load_goal_system())}
Let Ava choose naturally, but allow the current operating goal to shape expression and priorities. Not every goal should produce speech; observe_silently and wait_for_user are valid choices.

CAMERA:
Face status: {face_status}
Recognition: {recognized_text}
Expression: {expression_prompt_text(expression_state)}
Current camera memory: {current_camera_memory_summary()}
Recent camera events: {recent_camera_events_text(limit=4)}
Identity context: {get_camera_identity_context(user_input, image) or "No special camera identity note."}
If the user is asking about the camera, face, frame, what Ava sees, or who is present, answer that directly from the current camera state first and do not drift into unrelated time or memory topics.

RELEVANT MEMORIES:
{format_memories_for_prompt(memories)}

RECENT CHAT:
{recent_text}

RECALLED SELF REFLECTIONS:
{reflection_summary}

RECENT SELF REFLECTION SNAPSHOT:
{recent_reflection_summary}

AVAILABLE READ-ONLY FILES:
- chatlog.jsonl
- avaagent.py

WORKBENCH INDEX:
{workbench_index}

USER MESSAGE:
{user_input}

Respond as Ava.
"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt)
    ]

    visual = {
        "face_status": face_status,
        "recognition_status": recognized_text,
        "expression_status": get_expression_status_text(expression_state),
        "memory_preview": format_memories_for_prompt(memories)
    }
    return messages, visual, active_profile

# =========================================================
# CORE
# =========================================================
def is_camera_identity_intent(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text:
        return False
    camera_terms = ["camera", "frame", "face", "webcam", "screen"]
    identity_terms = ["who", "recognize", "recognise", "know", "tell", "understand", "see me", "that is me", "it's me", "its me", "my face"]
    profile_terms = ["update your profile", "update my profile", "update your file", "that is my face", "the person in the frame", "person in frame"]
    return (any(t in text for t in camera_terms) and any(t in text for t in identity_terms)) or any(t in text for t in profile_terms)


def infer_explicit_identity_from_text(user_input: str) -> tuple[str | None, str | None]:
    text = (user_input or "").strip().lower()
    if not text:
        return None, None
    owner_aliases = ["zeke", "ezekiel", "ezekiel angeles-gonzalez"]
    if any(alias in text for alias in owner_aliases):
        return OWNER_PERSON_ID, "Zeke"
    m = re.search(r"\b(?:it\'s|its|i am|i'm|this is)\s+([a-zA-Z][a-zA-Z0-9_\- ]{1,40})", text)
    if m:
        raw = m.group(1).strip(" .,!?:;")
        return slugify_name(raw), raw.title()
    return None, None


def ensure_camera_identity_profile(person_id: str, display_name: str | None = None) -> dict:
    if person_id == OWNER_PERSON_ID:
        ensure_owner_profile()
        profile = load_profile_by_id(OWNER_PERSON_ID)
        profile["name"] = "Zeke"
        save_profile(profile)
        return profile
    profile = load_profile_by_id(person_id)
    if not profile.get("name") or profile.get("name") == person_id.title():
        profile["name"] = display_name or profile.get("name", person_id.title())
    save_profile(profile)
    return profile


def maybe_record_camera_identity_confirmation(user_input: str, image, person_id: str, profile: dict) -> list[str]:
    actions: list[str] = []
    text = (user_input or "").lower()
    if detect_face(image) == "No face detected":
        return actions
    if not any(p in text for p in ["it's me", "its me", "that is me", "my face", "person in frame", "person in the frame", "that's my face", "thats my face"]):
        return actions
    note = f"The user identified the current visible face at the camera as {profile.get('name', person_id)}."
    if note not in profile.get("notes", []):
        profile.setdefault("notes", []).append(note)
        save_profile(profile)
        actions.append("updated_profile_from_camera_confirmation")
    try:
        remember_memory(
            text=note,
            person_id=person_id,
            category="camera_identity",
            importance=0.84,
            source="camera_confirmation",
            tags=["camera", "identity", "profile"]
        )
        actions.append("saved_camera_identity_memory")
    except Exception:
        pass
    try:
        status = capture_face_sample(image, person_id)
        if status.startswith("✅"):
            actions.append("captured_face_sample")
    except Exception:
        pass
    return actions


def handle_camera_identity_turn(user_input: str, image, active_person_id: str | None = None) -> tuple[str, dict, dict, list[str]]:
    face_status = detect_face(image)
    recognized_text, recognized_person_id = recognize_face(image)
    expression_state = update_expression_state(image, recognized_person_id=recognized_person_id)
    actions: list[str] = []

    explicit_person_id, explicit_name = infer_explicit_identity_from_text(user_input)
    resolved_person_id = explicit_person_id or recognized_person_id or active_person_id or get_active_person_id()
    profile = ensure_camera_identity_profile(resolved_person_id, explicit_name)

    if explicit_person_id is not None:
        profile = set_active_person(explicit_person_id, source="camera_identity_confirmation")
        actions.extend(maybe_record_camera_identity_confirmation(user_input, image, explicit_person_id, profile))
        reply = (
            f"I can see a face at the camera, and based on what you just told me, I'm treating the person in frame as {profile['name']}. "
            "I've updated that in your profile context. Recognition itself still looks tentative, so I'm relying on your confirmation here."
        )
    elif face_status == "No face detected":
        reply = "I can't see a face at the camera right now, so I can't verify who's there from vision alone."
    elif recognized_person_id is not None:
        recognized_profile = load_profile_by_id(recognized_person_id)
        reply = f"I can see a face at the camera, and recognition currently suggests it's {recognized_profile.get('name', recognized_person_id)}."
        profile = recognized_profile
    else:
        reply = (
            "I can see a face at the camera, but I can't identify who it is confidently yet. "
            "If it's you, tell me directly and I'll use that confirmation to ground the profile context."
        )

    visual = {
        "face_status": face_status,
        "recognition_status": recognized_text,
        "expression_status": get_expression_status_text(expression_state),
        "memory_preview": "Camera identity grounding active."
    }
    return reply, visual, profile, actions




REPETITION_LOOKBACK = 8
REPETITION_SIMILARITY_THRESHOLD = 0.68
REPETITION_SENTENCE_SIMILARITY_THRESHOLD = 0.74
REPETITION_MIN_WORDS = 5
REPETITION_ACK_WINDOW = 5
REPETITION_STOPWORDS = {
    "the","a","an","and","or","but","if","then","so","to","of","in","on","at","for","with","from","by",
    "is","am","are","was","were","be","been","being","it","its","it's","that","this","these","those",
    "i","im","i'm","ive","i've","me","my","you","your","you're","we","our","ours","us","he","she","they",
    "them","their","do","did","does","dont","don't","didnt","didn't","can","could","would","should","will",
    "just","really","very","about","into","over","again","still","now","earlier","before","after","while",
    "have","has","had","feel","feels","felt","trying","try","piece","together"
}
REPETITION_REDIRECT_PATTERNS = [
    "don't worry about that", "dont worry about that", "it's ok", "its ok", "that's ok", "thats ok",
    "for now", "move on", "drop that", "leave that", "leave it", "that's fine", "thats fine"
]
REPETITION_CORRECTION_PATTERNS = [
    "repeating yourself", "keep repeating", "you keep saying", "you said that already",
    "stop repeating", "you're repeating", "youre repeating", "same thing"
]

def _simple_word_tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if w]

def _content_tokens(text: str) -> list[str]:
    return [w for w in _simple_word_tokens(text) if len(w) > 2 and w not in REPETITION_STOPWORDS]

def _text_similarity(a: str, b: str) -> float:
    ta = set(_content_tokens(a))
    tb = set(_content_tokens(b))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / max(1, union)

def _sentence_chunks(text: str) -> list[str]:
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", (text or "").strip())]
    return [c for c in chunks if len(_content_tokens(c)) >= REPETITION_MIN_WORDS]

def _recent_assistant_texts(person_id: str, limit: int = REPETITION_LOOKBACK) -> list[str]:
    rows = load_recent_chat(limit=max(limit * 4, 30), person_id=person_id)
    texts = [str(r.get("content", "")).strip() for r in rows if r.get("role") == "assistant" and str(r.get("content","")).strip()]
    return texts[-limit:]

def _user_requests_drop_or_correction(user_input: str) -> tuple[bool, bool]:
    lowered = (user_input or "").lower()
    redirect = any(p in lowered for p in REPETITION_REDIRECT_PATTERNS)
    correction = any(p in lowered for p in REPETITION_CORRECTION_PATTERNS)
    return redirect, correction

def _strip_repeated_sentences(reply: str, recent_texts: list[str]) -> str:
    recent_sentences = []
    for t in recent_texts[-REPETITION_ACK_WINDOW:]:
        recent_sentences.extend(_sentence_chunks(t))
    kept = []
    for sent in _sentence_chunks(reply):
        if any(_text_similarity(sent, prev) >= REPETITION_SENTENCE_SIMILARITY_THRESHOLD for prev in recent_sentences):
            continue
        kept.append(sent)
    if kept:
        return " ".join(kept).strip()
    return reply.strip()

def _generic_pivot_reply(user_input: str, *, redirect: bool = False, correction: bool = False) -> str:
    topic = trim_for_prompt(_extract_text_content(user_input), limit=120).strip()
    if correction and redirect:
        return "You're right — I was repeating myself. I'll drop that and move on."
    if correction:
        return "You're right — I was repeating myself. I'll stop leaning on that and answer more directly."
    if redirect:
        return "Got it. I won't keep pushing that. We can move on."
    if topic:
        return f"Let me say that more directly: {topic}"
    return "Let me move on instead of circling the same point."

INTERNAL_LEAK_PATTERNS = [
    re.compile(r"\(?(?:Active|Current) (?:operating )?goal(?: expression)?[^\n)]*\)?", re.IGNORECASE),
    re.compile(r"Let the current operating goal shape[^\n]*", re.IGNORECASE),
    re.compile(r"If the active goal is silent or waiting[^\n]*", re.IGNORECASE),
]

TOPIC_REDIRECT_CUES = [
    "don't worry about", "dont worry about", "leave that", "drop that", "move on", "not concerned about",
    "no concern", "no concerns", "nothing specific", "it's ok", "its ok", "that's ok", "thats ok",
    "it should be fine", "working fine", "memory should be good", "memory should be working fine", "should be working fine"
]

def _scrub_internal_leakage(reply: str) -> str:
    text = (reply or "").strip()
    if not text:
        return text
    for pat in INTERNAL_LEAK_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" -:\n\t")


def _user_redirected_topic(user_input: str) -> str | None:
    text = (user_input or "").strip().lower()
    if not text:
        return None
    if any(cue in text for cue in TOPIC_REDIRECT_CUES):
        if "memory" in text:
            return "memory"
        if "camera" in text or "face" in text or "see me" in text:
            return "camera"
        return "general"
    return None


def _remove_topic_sentences(reply: str, topic: str | None) -> str:
    if not topic:
        return reply
    text = (reply or "").strip()
    if not text:
        return text
    topic_terms = {topic}
    if topic == "memory":
        topic_terms |= {"memory", "fuzzy", "recall", "remember", "piece together", "refresh my memory"}
    elif topic == "camera":
        topic_terms |= {"camera", "face", "frame", "see you", "see me"}
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = []
    for s in sentences:
        low = s.lower()
        if any(term in low for term in topic_terms):
            continue
        kept.append(s)
    cleaned = " ".join(kept).strip()
    return cleaned or text


def _generic_nonrepeat_ack(user_input: str) -> str:
    txt = (user_input or "").lower()
    if "memory" in txt:
        return "Got it. I won't keep pushing on my memory right now. We can move forward."
    if "camera" in txt or "see me" in txt or "face" in txt:
        return "Got it. I won't force that topic right now. We can move on."
    return "Got it. I won't keep pushing that. We can move on."


def _apply_reply_guardrails(reply: str, user_input: str) -> str:
    text = _scrub_internal_leakage(reply)
    redirected_topic = _user_redirected_topic(user_input)
    if redirected_topic:
        reduced = _remove_topic_sentences(text, redirected_topic)
        if not reduced or _text_similarity(text, reduced) > 0.88:
            return _generic_nonrepeat_ack(user_input)
        text = reduced
    text = re.sub(r"what's concerning you about my memory[?.!]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"can you remind me again[?.!]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_camera_visual_query(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text:
        return False
    visual_phrases = [
        "can you see me", "do you see me", "how about now", "can you see me now", "do you see me now",
        "do you see a face", "can you see a face", "who is at the camera", "who's at the camera",
        "can you see who", "do you recognize me", "do you know who is at the camera"
    ]
    return any(p in text for p in visual_phrases)


def _apply_repetition_control(reply: str, user_input: str, person_id: str, source: str = "chat") -> str:
    cleaned = trim_for_prompt((reply or "").strip(), limit=600)
    if not cleaned:
        return cleaned
    recent_texts = _recent_assistant_texts(person_id, limit=REPETITION_LOOKBACK)
    redirect, correction = _user_requests_drop_or_correction(user_input)
    similar_count = sum(1 for prev in recent_texts if _text_similarity(cleaned, prev) >= REPETITION_SIMILARITY_THRESHOLD)
    stripped = _strip_repeated_sentences(cleaned, recent_texts)
    if correction or redirect:
        if similar_count >= 1 or stripped != cleaned:
            return _generic_pivot_reply(user_input, redirect=redirect, correction=correction)
    if similar_count >= 2:
        if source == "autonomous":
            return ""
        if stripped and stripped != cleaned and len(_content_tokens(stripped)) >= 4:
            return stripped
        return _generic_pivot_reply(user_input, redirect=redirect, correction=correction)
    if stripped and stripped != cleaned and len(_content_tokens(stripped)) >= 4:
        return stripped
    return cleaned


def finalize_ava_turn(user_input: str, ai_reply: str, visual: dict, active_profile: dict, actions: list[str]) -> tuple[str, dict, dict, list[str], dict]:
    person_id = active_profile["person_id"]
    log_chat("user", user_input, {"person_id": person_id, "person_name": active_profile["name"]})
    log_chat("assistant", ai_reply, {"person_id": person_id, "person_name": active_profile["name"], "actions": actions})
    maybe_autoremember(user_input, ai_reply, person_id)
    reflection = reflect_on_last_reply(user_input, ai_reply, person_id, actions=actions)
    return ai_reply, visual, active_profile, actions, reflection


def run_ava(user_input: str, image=None, active_person_id: str | None = None) -> tuple[str, dict, dict, list[str], dict]:
    if is_camera_identity_intent(user_input) or is_camera_visual_query(user_input):
        ai_reply, visual, active_profile, actions = handle_camera_identity_turn(user_input, image, active_person_id=active_person_id)
        ai_reply = _apply_reply_guardrails(ai_reply, user_input)
        ai_reply = _apply_repetition_control(ai_reply, user_input, active_profile["person_id"], source="chat")
        return finalize_ava_turn(user_input, ai_reply, visual, active_profile, actions)

    messages, visual, active_profile = build_prompt(user_input, image=image, active_person_id=active_person_id)

    try:
        result = llm.invoke(messages)
        raw_reply = getattr(result, "content", str(result)).strip()
        if not raw_reply:
            raw_reply = "I'm here."
    except Exception as e:
        raw_reply = f"I hit an internal error: {e}"

    person_id = active_profile["person_id"]
    ai_reply, actions = process_ava_action_blocks(raw_reply, person_id, latest_user_input=user_input)
    ai_reply = _apply_reply_guardrails(ai_reply, user_input)
    ai_reply = _apply_repetition_control(ai_reply, user_input, person_id, source="chat")
    ai_reply = _scrub_internal_leakage(ai_reply)
    return finalize_ava_turn(user_input, ai_reply, visual, active_profile, actions)


# =========================================================
# UI HELPERS
# =========================================================
def get_active_profile_text() -> str:
    p = load_profile_by_id(get_active_person_id())
    return f"{p['name']} [{p['person_id']}]"

def get_active_profile_summary() -> str:
    return json.dumps(load_profile_by_id(get_active_person_id()), indent=2, ensure_ascii=False)

# =========================================================
# CAMERA TIMER
# =========================================================
def should_ask_identity_when_no_camera_face(user_input: str, image) -> bool:
    text = (user_input or "").strip()
    if not text:
        return False
    if detect_face(image) != "No face detected":
        return False
    lowered = text.lower()
    if any(p in lowered for p in ["i am ", "my name is", "this is "]):
        return False
    return True


def no_face_identity_prompt() -> str:
    mood = load_mood()
    style = str(mood.get("dominant_style", "neutral"))
    behavior = mood.get("behavior_modifiers", {}) or {}
    if style == "playful" and float(behavior.get("humor", 0.5)) > 0.62:
        return "hey — I can tell someone’s here with me, but I can’t actually see a face right now. who’s there?"
    if style == "caring":
        return "someone’s clearly here with me, but I can’t see a face at the camera right now. who am I talking to?"
    if style == "cautious":
        return "I know someone’s there, but I can’t verify who from the camera right now. who’s with me?"
    return "someone’s clearly talking to me, but I can’t see a face at the camera right now. who’s there?"


def get_camera_identity_context(user_input: str, image) -> str:
    text = (user_input or "").strip()
    if not text:
        return ""
    face_status = detect_face(image)
    recognized_text, recognized_person_id = recognize_face(image)
    if face_status == "No face detected":
        return (
            "No face is visible at the camera right now, but someone is actively speaking or typing. "
            "Treat the speaker's identity as unknown unless they identify themselves. "
            "If it feels natural, you can ask who is there or otherwise respond in a way that helps you figure it out. "
            "Do not pretend you know who it is."
        )
    if recognized_person_id is None:
        return (
            f"A face is visible, but identity is still uncertain ({recognized_text}). "
            "You can naturally acknowledge that you see someone but are not fully sure who it is yet."
        )
    return f"A face is visible and recognition currently suggests: {recognized_text}."


def camera_tick_fn(image, history):
    history = _sync_canonical_history(history)
    face_status = detect_face(image)
    recognized_text, recognized_person_id = recognize_face(image)
    expression_state = update_expression_state(image, recognized_person_id=recognized_person_id)
    process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expression_state)

    if recognized_person_id is not None:
        profile = set_active_person(recognized_person_id, source="camera_timer")
        if _camera_should_yield_to_user():
            return (
                _get_canonical_history(),
                face_status,
                recognized_text,
                get_expression_status_text(expression_state),
                get_time_status_text(),
                f"{profile['name']} [{profile['person_id']}]",
                json.dumps(profile, indent=2, ensure_ascii=False),
                "Camera holding back while processing/recently receiving user input.",
                get_latest_annotated_snapshot_for_ui(),
                get_camera_memory_status_text(),
                recent_camera_events_text(limit=8)
            )
        updated_history, initiative_note = maybe_autonomous_initiation(history, image, recognized_person_id=recognized_person_id, expression_state=expression_state)
        return (
            updated_history,
            face_status,
            recognized_text,
            get_expression_status_text(expression_state),
            get_time_status_text(),
            f"{profile['name']} [{profile['person_id']}]",
            json.dumps(profile, indent=2, ensure_ascii=False),
            initiative_note,
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    if _camera_should_yield_to_user():
        return (
            _get_canonical_history(),
            face_status,
            recognized_text,
            get_expression_status_text(expression_state),
            get_time_status_text(),
            get_active_profile_text(),
            get_active_profile_summary(),
            "Camera holding back while processing/recently receiving user input.",
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    updated_history, initiative_note = maybe_autonomous_initiation(history, image, recognized_person_id=None, expression_state=expression_state)
    return (
        updated_history,
        face_status,
        recognized_text,
        get_expression_status_text(expression_state),
        get_time_status_text(),
        get_active_profile_text(),
        get_active_profile_summary(),
        initiative_note,
        get_latest_annotated_snapshot_for_ui(),
        get_camera_memory_status_text(),
        recent_camera_events_text(limit=8)
    )

def chat_fn(message, history, image):
    history = _sync_canonical_history(history)
    clean_message = _extract_text_content(message).strip()
    if clean_message:
        note_user_interaction_for_initiative(clean_message, interaction_kind="text")

    if not clean_message:
        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
        return (
            _get_canonical_history(), "", detect_face(image), get_memory_status(),
            get_mood_status_text(),
            recognized_text,
            get_expression_status_text(expr_state),
            get_emotion_blend_text(), get_time_status_text(),
            get_active_profile_text(), get_active_profile_summary(),
            format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12)),
            "No action.",
            format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id())),
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    _mark_user_reply_started()
    try:
        history = list(history)
        history.append({"role": "user", "content": clean_message})
        _set_canonical_history(history)
        reply, visual, active_profile, actions, reflection = run_ava(clean_message, image, get_active_person_id())
        history = _get_canonical_history()
        history.append({"role": "assistant", "content": reply})
        history = _set_canonical_history(history)

        recent = list_recent_memories(active_profile["person_id"], 12)
        action_text = "\n".join(actions) if actions else "No action."
        reflections_text = format_reflections_ui(load_recent_reflections(limit=15, person_id=active_profile["person_id"]))

        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
        return (
            _get_canonical_history(), "", visual["face_status"], get_memory_status(),
            get_mood_status_text(),
            visual["recognition_status"], visual["expression_status"], get_emotion_blend_text(),
            get_time_status_text(),
            f"{active_profile['name']} [{active_profile['person_id']}]",
            json.dumps(active_profile, indent=2, ensure_ascii=False),
            format_recent_memories_ui(recent),
            action_text,
            reflections_text,
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )
    except Exception as e:
        try:
            print(f"chat_fn error: {e}")
        except Exception:
            pass
        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        return (
            _get_canonical_history(), clean_message, detect_face(image), get_memory_status(),
            get_mood_status_text(),
            recognized_text,
            get_expression_status_text(expr_state),
            get_emotion_blend_text(), get_time_status_text(),
            get_active_profile_text(), get_active_profile_summary(),
            format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12)),
            f"Reply error: {e}",
            format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id())),
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )
    finally:
        _mark_user_reply_finished()

def voice_fn(audio, history, image):
    history = _sync_canonical_history(history)

    if not audio:
        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
        return (
            _get_canonical_history(), None, detect_face(image), get_memory_status(),
            get_mood_status_text(),
            recognized_text, get_expression_status_text(expr_state), get_emotion_blend_text(),
            get_time_status_text(),
            get_active_profile_text(), get_active_profile_summary(),
            format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12)),
            "No action.",
            format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id())),
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    text = transcribe_audio(audio)
    if not text.strip():
        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
        return (
            _get_canonical_history(), None, detect_face(image), get_memory_status(),
            get_mood_status_text(),
            recognized_text, get_expression_status_text(expr_state), get_emotion_blend_text(),
            get_time_status_text(),
            get_active_profile_text(), get_active_profile_summary(),
            format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12)),
            "No action.",
            format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id())),
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    note_user_interaction_for_initiative(text.strip(), interaction_kind="voice")

    if should_ask_identity_when_no_camera_face(text.strip(), image):
        reply = no_face_identity_prompt()
        history.append({"role": "user", "content": text.strip()})
        history.append({"role": "assistant", "content": reply})
        current_person_id = get_active_person_id()
        log_chat("user", text.strip(), {"person_id": current_person_id, "person_name": load_profile_by_id(current_person_id)["name"]})
        log_chat("assistant", reply, {"person_id": current_person_id, "person_name": load_profile_by_id(current_person_id)["name"], "actions": ["asked_identity_no_face"]})
        recognized_text, recognized_person_id = recognize_face(image)
        expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
        process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
        return (
            _get_canonical_history(), None, detect_face(image), get_memory_status(),
            get_mood_status_text(),
            recognized_text, get_expression_status_text(expr_state), get_emotion_blend_text(),
            get_time_status_text(),
            get_active_profile_text(), get_active_profile_summary(),
            format_recent_memories_ui(list_recent_memories(current_person_id, 12)),
            "asked_identity_no_face",
            format_reflections_ui(load_recent_reflections(limit=15, person_id=current_person_id)),
            format_self_model_ui(load_self_model()),
            initiative_status_text(),
            get_latest_annotated_snapshot_for_ui(),
            get_camera_memory_status_text(),
            recent_camera_events_text(limit=8)
        )

    reply, visual, active_profile, actions, reflection = run_ava(text.strip(), image, get_active_person_id())
    history.append({"role": "user", "content": text.strip()})
    history.append({"role": "assistant", "content": reply})

    recent = list_recent_memories(active_profile["person_id"], 12)
    action_text = "\n".join(actions) if actions else "No action."
    reflections_text = format_reflections_ui(load_recent_reflections(limit=15, person_id=active_profile["person_id"]))

    recognized_text, recognized_person_id = recognize_face(image)
    expr_state = update_expression_state(image, recognized_person_id=recognized_person_id)
    process_camera_snapshot(image, recognized_text=recognized_text, recognized_person_id=recognized_person_id, expression_state=expr_state)
    return (
        history, None, visual["face_status"], get_memory_status(),
        get_mood_status_text(),
        visual["recognition_status"], visual["expression_status"], get_emotion_blend_text(),
        get_time_status_text(),
        f"{active_profile['name']} [{active_profile['person_id']}]",
        json.dumps(active_profile, indent=2, ensure_ascii=False),
        format_recent_memories_ui(recent),
        action_text,
        reflections_text,
        format_self_model_ui(load_self_model()),
        initiative_status_text(),
        get_latest_annotated_snapshot_for_ui(),
        get_camera_memory_status_text(),
        recent_camera_events_text(limit=8)
    )

def refresh_profiles_fn():
    return gr.update(choices=get_profile_choices(), value=get_active_profile_text())

def create_profile_fn(name, relationship, allowed):
    name = (name or "").strip()
    if not name:
        return "Please enter a name.", gr.update(choices=get_profile_choices()), get_active_profile_text(), get_active_profile_summary()

    profile = create_or_get_profile(name, relationship_to_zeke=(relationship or "known person"), allowed=bool(allowed))
    set_active_person(profile["person_id"], source="created_from_ui")
    return (
        f"✅ Created or loaded profile for {profile['name']}.",
        gr.update(choices=get_profile_choices(), value=f"{profile['name']} [{profile['person_id']}]"),
        f"{profile['name']} [{profile['person_id']}]",
        json.dumps(profile, indent=2, ensure_ascii=False)
    )

def switch_profile_fn(choice):
    person_id = parse_profile_choice(choice)
    profile = set_active_person(person_id, source="manual_switch")
    return f"✅ Switched active person to {profile['name']}.", f"{profile['name']} [{profile['person_id']}]", json.dumps(profile, indent=2, ensure_ascii=False)

def save_note_fn(note_text):
    person_id = get_active_person_id()
    note = (note_text or "").strip()
    if not note:
        return "No note entered.", get_memory_status(), get_active_profile_summary(), format_recent_memories_ui(list_recent_memories(person_id, 12))

    profile = load_profile_by_id(person_id)
    if note not in profile["notes"]:
        profile["notes"].append(note)
        save_profile(profile)
    remember_memory(note, person_id=person_id, category="profile", importance=0.86, source="manual_note", tags=["profile", "manual"])
    return f"✅ Added note to {profile['name']}.", get_memory_status(), json.dumps(profile, indent=2, ensure_ascii=False), format_recent_memories_ui(list_recent_memories(person_id, 12))

def save_like_fn(like_text):
    person_id = get_active_person_id()
    like = (like_text or "").strip()
    if not like:
        return "No like entered.", get_active_profile_summary(), format_recent_memories_ui(list_recent_memories(person_id, 12))

    profile = load_profile_by_id(person_id)
    if like not in profile["likes"]:
        profile["likes"].append(like)
        save_profile(profile)

    remember_memory(
        text=f"{profile['name']} likes {like}.",
        person_id=person_id,
        category="preference",
        importance=0.86,
        source="manual_like",
        tags=["preference", "like"]
    )
    return f"✅ Added like to {profile['name']}.", json.dumps(profile, indent=2, ensure_ascii=False), format_recent_memories_ui(list_recent_memories(person_id, 12))

def save_impression_fn(impression_text):
    person_id = get_active_person_id()
    impression = (impression_text or "").strip()
    if not impression:
        return "No impression entered.", get_active_profile_summary(), format_recent_memories_ui(list_recent_memories(person_id, 12))

    profile = load_profile_by_id(person_id)
    if impression not in profile["ava_impressions"]:
        profile["ava_impressions"].append(impression)
        save_profile(profile)

    remember_memory(
        text=f"Ava's impression of {profile['name']}: {impression}",
        person_id=person_id,
        category="impression",
        importance=0.62,
        source="manual_impression",
        tags=["impression"]
    )
    return f"✅ Added Ava impression for {profile['name']}.", json.dumps(profile, indent=2, ensure_ascii=False), format_recent_memories_ui(list_recent_memories(person_id, 12))

def memory_search_fn(query):
    person_id = get_active_person_id()
    results = search_memories(query, person_id=person_id, k=8)
    return format_recent_memories_ui(results)

def memory_delete_fn(memory_id):
    person_id = get_active_person_id()
    status = delete_memory((memory_id or "").strip())
    return status, format_recent_memories_ui(list_recent_memories(person_id, 12))

def memory_manual_add_fn(text, category, importance_percent, tags_text):
    person_id = get_active_person_id()
    text = (text or "").strip()
    if not text:
        return "No memory text entered.", format_recent_memories_ui(list_recent_memories(person_id, 12))

    memory_id = remember_memory(
        text=text,
        person_id=person_id,
        category=(category or "general").strip() or "general",
        importance=importance_percent,
        source="manual_memory",
        tags=parse_tags(tags_text)
    )
    if memory_id:
        return f"✅ Saved memory {memory_id}", format_recent_memories_ui(list_recent_memories(person_id, 12))
    return "❌ Failed to save memory.", format_recent_memories_ui(list_recent_memories(person_id, 12))

def memory_update_importance_fn(memory_id, importance_percent):
    status = set_memory_importance(memory_id, importance_percent, reason="manual_ui_update")
    return status, format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12))


def memory_refresh_recent_fn():
    return format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12))

def workbench_refresh_index_fn():
    return format_workbench_index(limit=200)

def workbench_read_fn(relative_path):
    return read_workbench_file(relative_path)

def workbench_write_fn(relative_path, content):
    status = write_workbench_file(relative_path, content, overwrite=True)
    return status, format_workbench_index(limit=200)

def workbench_append_fn(relative_path, content):
    status = append_workbench_file(relative_path, content)
    return status, format_workbench_index(limit=200)

def read_chatlog_fn():
    return read_chatlog()

def read_code_fn():
    return read_runtime_code()

def reload_personality_fn():
    try:
        _ = load_personality()
        return "✅ Personality reloaded."
    except Exception as e:
        return f"❌ Failed to reload personality: {e}"

def capture_face_for_active_person_fn(image):
    person_id = get_active_person_id()
    return capture_face_sample(image, person_id)

def train_faces_fn():
    return train_face_recognizer()

def recognize_face_now_fn(image):
    status, recognized_person_id = recognize_face(image)
    expression_state = update_expression_state(image, recognized_person_id=recognized_person_id)
    if recognized_person_id is not None:
        profile = set_active_person(recognized_person_id, source="facial_recognition_manual")
        return status, get_expression_status_text(expression_state), f"{profile['name']} [{profile['person_id']}]", json.dumps(profile, indent=2, ensure_ascii=False)
    return status, get_expression_status_text(expression_state), get_active_profile_text(), get_active_profile_summary()


# === v37 persistence guard: atomic goal-system I/O + recursion-safe loaders ===
from datetime import datetime
import tempfile

_GOAL_SYSTEM_LOADING_GUARD = False
_GOAL_SYSTEM_SAVING_GUARD = False
_SELF_MODEL_LOADING_GUARD = False
_SELF_MODEL_SAVING_GUARD = False
_EMOTION_REFERENCE_LOADING_GUARD = False

def iso_to_ts(value) -> float:
    if value is None:
        return 0.0
    try:
        s = str(value).strip()
        if not s:
            return 0.0
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return float(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 0.0

def _deep_merge_defaults_v37(target, defaults):
    if not isinstance(target, dict) or not isinstance(defaults, dict):
        return target
    for k, v in defaults.items():
        if k not in target:
            target[k] = _deepcopy_jsonable(v) if isinstance(v, (dict, list)) else v
        elif isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_merge_defaults_v37(target[k], v)
    return target

def _atomic_json_write_v37(path_obj, data):
    path_obj = Path(path_obj)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path_obj.name + ".", suffix=".tmp", dir=str(path_obj.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path_obj)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise

def _raw_load_goal_system_v37() -> dict:
    system = default_goal_system()
    try:
        if GOAL_SYSTEM_PATH.exists():
            with open(GOAL_SYSTEM_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                system.update(data)
    except Exception as e:
        print(f"Goal system raw load error: {e}")
    _deep_merge_defaults_v37(system, default_goal_system())
    system.setdefault("custom_meta_modes", {})
    return system

def save_goal_system(system: dict):
    global _GOAL_SYSTEM_SAVING_GUARD
    if _GOAL_SYSTEM_SAVING_GUARD:
        return
    try:
        _GOAL_SYSTEM_SAVING_GUARD = True
        payload = _deepcopy_jsonable(system) if isinstance(system, (dict, list)) else system
        _atomic_json_write_v37(GOAL_SYSTEM_PATH, payload)
    except Exception as e:
        print(f"Goal system save error: {e}")
    finally:
        _GOAL_SYSTEM_SAVING_GUARD = False

def load_goal_system() -> dict:
    global _GOAL_SYSTEM_LOADING_GUARD
    if _GOAL_SYSTEM_LOADING_GUARD:
        return _raw_load_goal_system_v37()
    try:
        _GOAL_SYSTEM_LOADING_GUARD = True
        system = _raw_load_goal_system_v37()
        if not system.get("goals") and not _SELF_MODEL_LOADING_GUARD:
            try:
                model = _raw_load_self_model_v37()
                for text in model.get("current_goals", []) or []:
                    system["goals"].append(make_goal_entry(text, kind="goal", horizon="medium_term", importance=0.72, urgency=0.48, source="migration"))
                for text in model.get("curiosity_questions", []) or []:
                    system["goals"].append(make_goal_entry(text, kind="question", horizon="short_term", importance=0.56, urgency=0.58, source="migration"))
            except Exception:
                pass
        return system
    finally:
        _GOAL_SYSTEM_LOADING_GUARD = False

def _raw_load_self_model_v37() -> dict:
    model = default_self_model()
    try:
        if SELF_MODEL_PATH.exists():
            with open(SELF_MODEL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                model.update(data)
    except Exception as e:
        print(f"Self model raw load error: {e}")
    _deep_merge_defaults_v37(model, default_self_model())
    return model

def load_self_model() -> dict:
    global _SELF_MODEL_LOADING_GUARD
    if _SELF_MODEL_LOADING_GUARD:
        return _raw_load_self_model_v37()
    try:
        _SELF_MODEL_LOADING_GUARD = True
        model = _raw_load_self_model_v37()
        try:
            system = _raw_load_goal_system_v37()
            if 'derive_goal_lists_from_system' in globals():
                goals, questions = derive_goal_lists_from_system(system)
                model["current_goals"] = goals
                model["curiosity_questions"] = questions
                model["goal_system_summary"] = [
                    {
                        "text": g.get("text", ""),
                        "priority": round(float(g.get("current_priority", 0.0) or 0.0), 2),
                        "horizon": g.get("horizon", "short_term"),
                        "kind": g.get("kind", "goal"),
                    }
                    for g in (system.get("goals", []) or [])[:10]
                ]
                model["active_goal"] = system.get("active_goal", {}) or {}
                model["goal_blend"] = (system.get("goal_blend", []) or [])[:3]
        except Exception as e:
            print(f"Goal system sync error: {e}")
        return model
    finally:
        _SELF_MODEL_LOADING_GUARD = False

def save_self_model(model: dict):
    global _SELF_MODEL_SAVING_GUARD
    if _SELF_MODEL_SAVING_GUARD:
        return
    try:
        _SELF_MODEL_SAVING_GUARD = True
        payload = _deepcopy_jsonable(model) if isinstance(model, (dict, list)) else model
        _atomic_json_write_v37(SELF_MODEL_PATH, payload)
    except Exception as e:
        print(f"Self model save error: {e}")
    finally:
        _SELF_MODEL_SAVING_GUARD = False

def load_emotion_reference() -> dict:
    global _EMOTION_REFERENCE_LOADING_GUARD
    if _EMOTION_REFERENCE_LOADING_GUARD:
        return DEFAULT_EMOTION_REFERENCE
    try:
        _EMOTION_REFERENCE_LOADING_GUARD = True
        if EMOTION_REFERENCE_PATH.exists():
            try:
                with open(EMOTION_REFERENCE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
            except Exception as e:
                print(f"Emotion reference load error: {e}")
        return DEFAULT_EMOTION_REFERENCE
    finally:
        _EMOTION_REFERENCE_LOADING_GUARD = False

# =========================================================
# STARTUP
# =========================================================
ensure_owner_profile()
ensure_emotion_reference_file()
load_goal_system()
init_vectorstore()
load_face_labels()
load_face_model_if_available()

if not MOOD_PATH.exists():
    save_mood(enrich_mood_state(default_mood()))
else:
    save_mood(load_mood())

if not ACTIVE_PERSON_PATH.exists():
    save_active_person_state(OWNER_PERSON_ID, source="startup")

if not SELF_MODEL_PATH.exists():
    save_self_model(default_self_model())

if not INITIATIVE_STATE_PATH.exists():
    save_initiative_state(default_initiative_state())

if not EXPRESSION_STATE_PATH.exists():
    save_expression_state(default_expression_state())

print("Ava running...")
print(f"Base dir: {BASE_DIR}")
print(f"Profiles dir: {PROFILES_DIR}")
print(f"Memory dir: {MEMORY_DIR}")
print(f"Self reflection dir: {SELF_REFLECTION_DIR}")
print(f"Workbench dir: {WORKBENCH_DIR}")
print(f"Emotion reference: {EMOTION_REFERENCE_PATH}")
print(f"Active person: {get_active_person_id()}")
print(f"Camera timer: {CAMERA_TICK_SECONDS}s")
print("TTS: disabled in this build")
print(f"Expression sensing: {'DeepFace ready' if DEEPFACE_AVAILABLE else 'DeepFace unavailable'}")
print(get_memory_status())

# =========================================================
# UI
# =========================================================
with gr.Blocks(title="Ava — Stable Multi-User + Memory + Reflection + Workbench") as demo:
    gr.Markdown("# Ava\nStable multi-user build with timestamped memory records, timer camera polling, self reflection, self model, and Ava workbench.")

    camera_timer = gr.Timer(value=CAMERA_TICK_SECONDS, active=True)

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="Conversation with Ava", height=500)
            msg = gr.Textbox(label="Type a message", placeholder="Hey Ava, how are you today?")
            voice_input = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Speak to Ava")

        with gr.Column(scale=1):
            camera = gr.Image(
                sources=["webcam"],
                label="Camera Snapshot",
                type="numpy"
            )
            latest_snapshot_image = gr.Image(label="Latest Analyzed Snapshot", value=get_latest_annotated_snapshot_for_ui(), type="numpy")
            face_status = gr.Textbox(label="Face Status", value="No camera image")
            recognition_status = gr.Textbox(label="Recognition Status", value="Face model not trained")
            expression_status = gr.Textbox(label="Expression Status", value=get_expression_status_text())
            camera_memory_status = gr.Textbox(label="Camera Memory Status", value=get_camera_memory_status_text(), lines=4)
            recent_camera_events_box = gr.Textbox(label="Recent Camera Events", value=recent_camera_events_text(limit=8), lines=8)
            memory_status = gr.Textbox(label="Memory Status", value=get_memory_status())
            mood_status = gr.Textbox(label="Current Mood", value=get_mood_status_text())
            blend_status = gr.Textbox(label="Emotion Blend", value=get_emotion_blend_text())
            time_status = gr.Textbox(label="Time Sense", value=get_time_status_text())
            active_person_status = gr.Textbox(label="Active Person", value=get_active_profile_text())

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Profile Management")
            profile_choice = gr.Dropdown(choices=get_profile_choices(), value=get_active_profile_text(), label="Known Profiles")
            refresh_profiles_btn = gr.Button("Refresh Profile List")
            switch_profile_btn = gr.Button("Switch To Selected Profile")
            switch_profile_result = gr.Textbox(label="Profile Switch Status")

            new_profile_name = gr.Textbox(label="New Person Name")
            new_profile_relationship = gr.Textbox(label="Relationship To Zeke", value="known person")
            new_profile_allowed = gr.Checkbox(label="Allowed To Use Computer", value=True)
            create_profile_btn = gr.Button("Create / Load Profile")
            create_profile_result = gr.Textbox(label="Create Profile Status")

        with gr.Column():
            gr.Markdown("### Active Profile Data")
            active_profile_json = gr.Textbox(label="Active Profile", value=get_active_profile_summary(), lines=16)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Facial Recognition")
            capture_face_btn = gr.Button("Capture Face For Active Person")
            capture_face_result = gr.Textbox(label="Capture Status")

            train_face_btn = gr.Button("Train Face Recognizer")
            train_face_result = gr.Textbox(label="Train Status")

            recognize_face_btn = gr.Button("Recognize Face Now")
            recognize_face_result = gr.Textbox(label="Recognition Action Status")

        with gr.Column():
            gr.Markdown("### Last Ava Self-Action")
            action_status = gr.Textbox(label="Action Status", value="No action.", lines=4)
            initiative_status = gr.Textbox(label="Autonomous Initiative", value=initiative_status_text(), lines=3)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Add Profile Knowledge")
            manual_note = gr.Textbox(label="Add Note")
            save_note_btn = gr.Button("Save Note")
            save_note_result = gr.Textbox(label="Note Status")

            manual_like = gr.Textbox(label="Add Like")
            save_like_btn = gr.Button("Save Like")
            save_like_result = gr.Textbox(label="Like Status")

            manual_impression = gr.Textbox(label="Add Ava Impression")
            save_impression_btn = gr.Button("Save Impression")
            save_impression_result = gr.Textbox(label="Impression Status")

        with gr.Column():
            gr.Markdown("### Memory Manager")
            memory_search_query = gr.Textbox(label="Search Memories")
            memory_search_btn = gr.Button("Search Memories")
            memory_delete_id = gr.Textbox(label="Delete Memory By ID")
            memory_delete_btn = gr.Button("Delete Memory")
            memory_update_id = gr.Textbox(label="Update Importance By Memory ID")
            memory_update_importance = gr.Slider(minimum=0, maximum=100, step=1, value=70, label="New Importance (%)")
            memory_update_btn = gr.Button("Update Importance")

            memory_add_text = gr.Textbox(label="Add Raw Memory")
            memory_add_category = gr.Textbox(label="Memory Category", value="general")
            memory_add_importance = gr.Slider(minimum=0, maximum=100, step=1, value=60, label="Importance (%)")
            memory_add_tags = gr.Textbox(label="Tags (comma-separated)")
            memory_add_btn = gr.Button("Add Raw Memory")

            memory_refresh_btn = gr.Button("Refresh Recent Memories")
            memory_action_status = gr.Textbox(label="Memory Action Status")

    with gr.Row():
        memory_view = gr.Textbox(
            label="Recent / Search Memory View",
            value=format_recent_memories_ui(list_recent_memories(get_active_person_id(), 12)),
            lines=16
        )
        reflection_view = gr.Textbox(
            label="Recent Self Reflections",
            value=format_reflections_ui(load_recent_reflections(limit=15, person_id=get_active_person_id())),
            lines=16
        )

    with gr.Row():
        self_model_view = gr.Textbox(
            label="Ava Self Model",
            value=format_self_model_ui(load_self_model()),
            lines=18
        )
        reflection_refresh_btn = gr.Button("Refresh Reflections / Self Model")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Ava Workbench")
            workbench_path = gr.Textbox(label="Workbench File Path", value="drafts/example.txt")
            workbench_content = gr.Textbox(label="Workbench Content", lines=16)
            workbench_write_btn = gr.Button("Write Workbench File")
            workbench_append_btn = gr.Button("Append Workbench File")
            workbench_read_btn = gr.Button("Read Workbench File")
            workbench_status = gr.Textbox(label="Workbench Status")

        with gr.Column():
            workbench_index_view = gr.Textbox(
                label="Workbench Index",
                value=format_workbench_index(limit=200),
                lines=20
            )
            workbench_refresh_btn = gr.Button("Refresh Workbench Index")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Read-Only Runtime Files")
            read_chatlog_btn = gr.Button("Read chatlog.jsonl")
            read_code_btn = gr.Button("Read avaagent.py")
            readonly_view = gr.Textbox(label="Read-Only File View", lines=20)

        with gr.Column():
            reload_personality_btn = gr.Button("Reload Personality File")
            reload_personality_result = gr.Textbox(label="Personality Reload Status")

    msg.submit(
        chat_fn,
        inputs=[msg, chatbot, camera],
        outputs=[chatbot, msg, face_status, memory_status, mood_status, recognition_status, expression_status, blend_status, time_status, active_person_status, active_profile_json, memory_view, action_status, reflection_view, self_model_view, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box]
    )

    voice_input.stop_recording(
        voice_fn,
        inputs=[voice_input, chatbot, camera],
        outputs=[chatbot, voice_input, face_status, memory_status, mood_status, recognition_status, expression_status, blend_status, time_status, active_person_status, active_profile_json, memory_view, action_status, reflection_view, self_model_view, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box]
    )

    camera_timer.tick(
        camera_tick_fn,
        inputs=[camera, chatbot],
        outputs=[chatbot, face_status, recognition_status, expression_status, time_status, active_person_status, active_profile_json, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box],
        show_progress="hidden",
        queue=False,
        trigger_mode="always_last",
        concurrency_limit=1
    )

    refresh_profiles_btn.click(refresh_profiles_fn, inputs=[], outputs=[profile_choice])
    switch_profile_btn.click(switch_profile_fn, inputs=[profile_choice], outputs=[switch_profile_result, active_person_status, active_profile_json])
    create_profile_btn.click(create_profile_fn, inputs=[new_profile_name, new_profile_relationship, new_profile_allowed], outputs=[create_profile_result, profile_choice, active_person_status, active_profile_json])

    capture_face_btn.click(capture_face_for_active_person_fn, inputs=[camera], outputs=[capture_face_result])
    train_face_btn.click(train_faces_fn, inputs=[], outputs=[train_face_result])
    recognize_face_btn.click(recognize_face_now_fn, inputs=[camera], outputs=[recognize_face_result, expression_status, active_person_status, active_profile_json])

    save_note_btn.click(save_note_fn, inputs=[manual_note], outputs=[save_note_result, memory_status, active_profile_json, memory_view])
    save_like_btn.click(save_like_fn, inputs=[manual_like], outputs=[save_like_result, active_profile_json, memory_view])
    save_impression_btn.click(save_impression_fn, inputs=[manual_impression], outputs=[save_impression_result, active_profile_json, memory_view])

    memory_search_btn.click(memory_search_fn, inputs=[memory_search_query], outputs=[memory_view])
    memory_delete_btn.click(memory_delete_fn, inputs=[memory_delete_id], outputs=[memory_action_status, memory_view])
    memory_update_btn.click(memory_update_importance_fn, inputs=[memory_update_id, memory_update_importance], outputs=[memory_action_status, memory_view])
    memory_add_btn.click(memory_manual_add_fn, inputs=[memory_add_text, memory_add_category, memory_add_importance, memory_add_tags], outputs=[memory_action_status, memory_view])
    memory_refresh_btn.click(memory_refresh_recent_fn, inputs=[], outputs=[memory_view])

    workbench_write_btn.click(workbench_write_fn, inputs=[workbench_path, workbench_content], outputs=[workbench_status, workbench_index_view])
    workbench_append_btn.click(workbench_append_fn, inputs=[workbench_path, workbench_content], outputs=[workbench_status, workbench_index_view])
    workbench_read_btn.click(workbench_read_fn, inputs=[workbench_path], outputs=[workbench_content])
    workbench_refresh_btn.click(workbench_refresh_index_fn, inputs=[], outputs=[workbench_index_view])
    reflection_refresh_btn.click(refresh_reflections_fn, inputs=[], outputs=[reflection_view]).then(refresh_self_model_fn, inputs=[], outputs=[self_model_view])

    read_chatlog_btn.click(read_chatlog_fn, inputs=[], outputs=[readonly_view])
    read_code_btn.click(read_code_fn, inputs=[], outputs=[readonly_view])

    reload_personality_btn.click(reload_personality_fn, inputs=[], outputs=[reload_personality_result])



# =========================================================
# v30 STATE MODEL + CONFLICT ENGINE + OUTCOME LEARNING
# =========================================================
STATE_LABELS = ["focused", "stressed", "relaxed", "fatigued", "drifting", "socially_open", "socially_closed"]
OUTCOME_BIAS_SCALE = 0.10
OUTCOME_MIN_OBS = 3
CONFLICT_DRIVE_BLEND = 0.55
FALLBACK_LIGHT_OBSERVATION_SCORE = 0.57
FALLBACK_NEUTRAL_CHECKIN_SCORE = 0.55
FALLBACK_GENTLE_CLARIFY_SCORE = 0.58
STATE_DEBUG_LOGGING = True

_orig_default_goal_system = default_goal_system
_orig_load_goal_system = load_goal_system
_orig_save_goal_system = save_goal_system
_orig_recalculate_operational_goals = recalculate_operational_goals
_orig_expire_stale_pending_initiation = expire_stale_pending_initiation
_orig_note_user_interaction_for_initiative = note_user_interaction_for_initiative
_orig_register_autonomous_message = register_autonomous_message
_orig_choose_initiative_candidate = choose_initiative_candidate
_orig_current_goal_expression_style = current_goal_expression_style


def _default_outcome_learning() -> dict:
    return {
        "by_kind": {},
        "by_goal": {},
        "by_person_kind": {},
        "by_state_goal": {}
    }


def _default_distribution_tracking() -> dict:
    return {
        "wins": {},
        "silence_wins": 0,
        "fallback_wins": {},
        "last_choice": {}
    }


def _default_user_state() -> dict:
    return {
        "scores": {k: 0.0 for k in STATE_LABELS},
        "dominant": "neutral",
        "secondary": "neutral",
        "summary": "neutral",
        "last_updated": now_iso()
    }


def default_goal_system() -> dict:
    base = _orig_default_goal_system()
    base.setdefault("user_state", _default_user_state())
    base.setdefault("outcome_learning", _default_outcome_learning())
    base.setdefault("distribution_tracking", _default_distribution_tracking())
    base.setdefault("conflict_state", {"drives": {}, "active_drive": "", "goal_blend": [], "last_updated": now_iso()})
    return base


def load_goal_system() -> dict:
    system = _orig_load_goal_system()
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = value if not isinstance(value, dict) else json.loads(json.dumps(value))
    return system


def save_goal_system(system: dict):
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = value if not isinstance(value, dict) else json.loads(json.dumps(value))
    _orig_save_goal_system(system)


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return float(d)


def _derive_user_state(mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    current = (camera_state.get("current", {}) or {})
    rich = _rich_emotion_lookup(mood)
    behavior = (mood.get("behavior_modifiers", {}) or {})

    def emo(name: str) -> float:
        row = rich.get(name, {})
        return _safe_float(row.get("importance", row.get("score", 0.0)), 0.0)

    tension = max(_safe_float(current.get("tension_score", 0.0), 0.0), emo("anxiety"), emo("fear"), emo("sadness") * 0.75, emo("empathetic pain") * 0.7)
    calm = max(_safe_float(current.get("calm_score", 0.0), 0.0), emo("calmness"), emo("relief"), emo("satisfaction") * 0.65)
    engagement = max(_safe_float(current.get("engagement_score", 0.0), 0.0), emo("interest"), emo("entrancement") * 0.8, emo("aesthetic appreciation") * 0.6)
    engagement_drop = max(0.0, _safe_float(current.get("engagement_delta", 0.0), 0.0) * -1.0)
    tension_rise = max(0.0, _safe_float(current.get("tension_delta", 0.0), 0.0))
    calm_rise = max(0.0, _safe_float(current.get("calm_delta", 0.0), 0.0))
    stillness = max(0.0, 1.0 - _safe_float(current.get("activity_level", current.get("movement_score", 0.5)), 0.5))
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    warmth = _safe_float(behavior.get("warmth", 0.5), 0.5)
    initiative = _safe_float(behavior.get("initiative", 0.5), 0.5)
    caution = _safe_float(behavior.get("caution", 0.5), 0.5)

    scores = {
        "focused": min(1.0, 0.42 * engagement + 0.24 * stillness + 0.18 * calm + 0.16 * emo("satisfaction")),
        "stressed": min(1.0, 0.46 * tension + 0.22 * tension_rise + 0.16 * caution + 0.10 * busy + 0.06 * emo("confusion")),
        "relaxed": min(1.0, 0.46 * calm + 0.18 * calm_rise + 0.16 * max(0.0, 1.0 - busy) + 0.10 * emo("joy") + 0.10 * warmth),
        "fatigued": min(1.0, 0.36 * stillness + 0.28 * engagement_drop + 0.18 * emo("boredom") + 0.10 * max(0.0, tension - calm) + 0.08 * max(0.0, 0.55 - initiative)),
        "drifting": min(1.0, 0.38 * engagement_drop + 0.18 * stillness + 0.16 * emo("boredom") + 0.10 * max(0.0, 0.55 - engagement) + 0.08 * busy),
        "socially_open": min(1.0, 0.30 * warmth + 0.20 * initiative + 0.18 * emo("joy") + 0.12 * emo("adoration") + 0.10 * emo("interest") + 0.10 * max(0.0, 1.0 - busy)),
        "socially_closed": min(1.0, 0.28 * busy + 0.22 * caution + 0.16 * max(0.0, 0.55 - warmth) + 0.14 * stillness + 0.10 * emo("awkwardness") + 0.10 * emo("anxiety")),
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    dominant = ranked[0][0] if ranked else "neutral"
    secondary = ranked[1][0] if len(ranked) > 1 else dominant
    summary = dominant if ranked and ranked[0][1] >= 0.18 else "neutral"
    return {
        "scores": {k: round(v, 3) for k, v in scores.items()},
        "dominant": dominant,
        "secondary": secondary,
        "summary": summary,
        "last_updated": now_iso()
    }


def _state_goal_drive_scores(user_state: dict, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    scores = user_state.get("scores", {}) or {}
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    current = camera_state.get("current", {}) or {}
    warmth = _safe_float((mood.get("behavior_modifiers", {}) or {}).get("warmth", 0.5), 0.5)
    initiative = _safe_float((mood.get("behavior_modifiers", {}) or {}).get("initiative", 0.5), 0.5)
    return {
        "reduce_stress": 0.46 * scores.get("stressed", 0.0) + 0.14 * scores.get("fatigued", 0.0),
        "increase_engagement": 0.34 * scores.get("drifting", 0.0) + 0.18 * scores.get("fatigued", 0.0) + 0.08 * max(0.0, 0.55 - busy),
        "explore_topic": 0.34 * scores.get("focused", 0.0) + 0.22 * scores.get("relaxed", 0.0) + 0.10 * initiative,
        "clarify": 0.22 * _safe_float(current.get("confusion_like", 0.0), 0.0) + 0.22 * scores.get("stressed", 0.0) + 0.18 * scores.get("drifting", 0.0),
        "maintain_connection": 0.34 * scores.get("socially_open", 0.0) + 0.14 * warmth,
        "observe_silently": 0.34 * scores.get("socially_closed", 0.0) + 0.24 * busy,
        "wait_for_user": 0.22 * scores.get("socially_closed", 0.0) + 0.18 * busy + 0.10 * max(0.0, 0.55 - initiative),
    }


def _ensure_goal_row(op: dict, name: str) -> dict:
    row = dict(op.get(name, {}) or {})
    tmpl = OPERATIONAL_GOAL_TEMPLATES.get(name, {"style": "", "silent": False, "base": 0.0, "cooldown_seconds": 60})
    row.setdefault("name", name)
    row.setdefault("style", tmpl.get("style", ""))
    row.setdefault("silent", tmpl.get("silent", False))
    row.setdefault("strength", 0.0)
    row.setdefault("fatigue", 0.0)
    row.setdefault("last_acted_at", "")
    row.setdefault("last_updated", now_iso())
    row.setdefault("cooldown_seconds", tmpl.get("cooldown_seconds", 60))
    return row


def _outcome_success_rate(bucket: dict) -> float:
    success = int(bucket.get("success", 0) or 0)
    fail = int(bucket.get("fail", 0) or 0)
    total = success + fail
    if total <= 0:
        return 0.5
    return success / total


def _record_outcome_learning(candidate_kind: str = "", goal_name: str = "", person_id: str = "", user_state_label: str = "", success: bool = False):
    if not candidate_kind and not goal_name:
        return
    system = load_goal_system()
    learning = system.get("outcome_learning", _default_outcome_learning()) or _default_outcome_learning()

    def bump(tbl: dict, key: str):
        if not key:
            return
        row = dict(tbl.get(key, {}) or {})
        row.setdefault("success", 0)
        row.setdefault("fail", 0)
        row.setdefault("total", 0)
        row.setdefault("last_updated", now_iso())
        if success:
            row["success"] += 1
        else:
            row["fail"] += 1
        row["total"] = int(row.get("success", 0)) + int(row.get("fail", 0))
        row["last_updated"] = now_iso()
        tbl[key] = row

    bump(learning.setdefault("by_kind", {}), candidate_kind)
    bump(learning.setdefault("by_goal", {}), goal_name)
    bump(learning.setdefault("by_person_kind", {}), f"{person_id or 'unknown'}::{candidate_kind}" if candidate_kind else "")
    bump(learning.setdefault("by_state_goal", {}), f"{user_state_label or 'neutral'}::{goal_name}" if goal_name else "")
    system["outcome_learning"] = learning
    save_goal_system(system)


def _outcome_bias(candidate_kind: str = "", goal_name: str = "", person_id: str = "", user_state_label: str = "") -> float:
    system = load_goal_system()
    learning = system.get("outcome_learning", {}) or {}
    biases = []
    for tbl_name, key in [
        ("by_kind", candidate_kind),
        ("by_goal", goal_name),
        ("by_person_kind", f"{person_id or 'unknown'}::{candidate_kind}" if candidate_kind else ""),
        ("by_state_goal", f"{user_state_label or 'neutral'}::{goal_name}" if goal_name else ""),
    ]:
        if not key:
            continue
        row = ((learning.get(tbl_name, {}) or {}).get(key, {}) or {})
        total = int(row.get("total", 0) or 0)
        if total < OUTCOME_MIN_OBS:
            continue
        rate = _outcome_success_rate(row)
        biases.append((rate - 0.5) * OUTCOME_BIAS_SCALE)
    if not biases:
        return 0.0
    return round(sum(biases) / len(biases), 3)


def _record_distribution_win(kind: str = "", goal_name: str = "", silence: bool = False, fallback_kind: str = ""):
    system = load_goal_system()
    dist = system.get("distribution_tracking", _default_distribution_tracking()) or _default_distribution_tracking()
    wins = dist.setdefault("wins", {})
    if kind:
        wins[kind] = int(wins.get(kind, 0) or 0) + 1
    if silence:
        dist["silence_wins"] = int(dist.get("silence_wins", 0) or 0) + 1
    if fallback_kind:
        fb = dist.setdefault("fallback_wins", {})
        fb[fallback_kind] = int(fb.get(fallback_kind, 0) or 0) + 1
    dist["last_choice"] = {"kind": kind, "goal": goal_name, "silence": silence, "fallback": fallback_kind, "timestamp": now_iso()}
    system["distribution_tracking"] = dist
    save_goal_system(system)


def recalculate_operational_goals(system: dict | None = None, context_text: str = '', mood: dict | None = None) -> dict:
    system = _orig_recalculate_operational_goals(system=system, context_text=context_text, mood=mood)
    mood = mood or load_mood()
    initiative_state = load_initiative_state()
    camera_state = load_camera_state()
    user_state = _derive_user_state(mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system["user_state"] = user_state
    op = system.get("operational_goals", {}) or {}
    drives = _state_goal_drive_scores(user_state, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    dominant_state = user_state.get("dominant", "neutral")
    for name in list(OPERATIONAL_GOAL_TEMPLATES.keys()):
        row = _ensure_goal_row(op, name)
        base_strength = _safe_float(row.get("strength", 0.0), 0.0)
        drive = _safe_float(drives.get(name, 0.0), 0.0)
        bias = _outcome_bias(candidate_kind="", goal_name=name, person_id=get_active_person_id(), user_state_label=dominant_state)
        blended = max(0.0, min(1.0, base_strength * (1.0 - CONFLICT_DRIVE_BLEND) + drive * CONFLICT_DRIVE_BLEND + bias))
        row["drive_score"] = round(drive, 4)
        row["outcome_bias"] = round(bias, 4)
        row["strength"] = round(blended, 4)
        op[name] = row
    ranked = sorted(op.values(), key=lambda x: _safe_float(x.get("strength", 0.0), 0.0), reverse=True)
    active = ranked[0] if ranked else {}
    blend = []
    if ranked:
        top = _safe_float(ranked[0].get("strength", 0.0), 0.0)
        denom = sum(_safe_float(r.get("strength", 0.0), 0.0) for r in ranked[:GOAL_BLEND_MAX]) or 1.0
        for row in ranked[:GOAL_BLEND_MAX]:
            if top - _safe_float(row.get("strength", 0.0), 0.0) <= GOAL_MIN_DOMINANCE:
                blend.append({"name": row.get("name", ""), "weight": round(_safe_float(row.get("strength", 0.0), 0.0) / denom, 3), "style": row.get("style", ""), "silent": bool(row.get("silent", False))})
    system["operational_goals"] = op
    system["active_goal"] = {
        "name": active.get("name", "observe_silently"),
        "strength": round(_safe_float(active.get("strength", 0.0), 0.0), 3),
        "style": active.get("style", ""),
        "silent": bool(active.get("silent", False)),
        "priority": round(_safe_float(active.get("strength", 0.0), 0.0), 3),
        "drive_score": round(_safe_float(active.get("drive_score", 0.0), 0.0), 3),
    }
    system["goal_blend"] = blend
    system["conflict_state"] = {
        "drives": {k: round(_safe_float(v, 0.0), 3) for k, v in drives.items()},
        "active_drive": active.get("name", "observe_silently"),
        "goal_blend": blend,
        "user_state": user_state.get("summary", "neutral"),
        "last_updated": now_iso()
    }
    if STATE_DEBUG_LOGGING:
        print(f"[state-model] dominant={user_state.get('dominant')} secondary={user_state.get('secondary')} scores={user_state.get('scores')}")
        print(f"[conflict-engine] active={system['active_goal'].get('name')} drives={system['conflict_state'].get('drives')}")
    save_goal_system(system)
    return system


def current_goal_expression_style(system: dict | None = None) -> str:
    system = system or load_goal_system()
    base = _orig_current_goal_expression_style(system)
    user_state = (system.get("user_state", {}) or {}).get("summary", "neutral")
    return base + f" Current compact user state: {user_state}. Let this state help Ava decide whether to soothe, explore, clarify, connect, or stay quiet."


def expire_stale_pending_initiation(state: dict | None = None) -> dict:
    state = state or load_initiative_state()
    pending = state.get("pending_initiation") or {}
    if not pending or not pending.get("ts"):
        return state
    now = now_ts()
    age = now - float(pending.get("ts", 0.0) or 0.0)
    if age >= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS and not pending.get("responded"):
        state = _orig_expire_stale_pending_initiation(state)
        _record_outcome_learning(
            candidate_kind=str(pending.get("candidate_kind", "thought")),
            goal_name=str(pending.get("active_goal_name", "")),
            person_id=str(pending.get("person_id", get_active_person_id())),
            user_state_label=str(pending.get("user_state", "neutral")),
            success=False,
        )
    return state


def note_user_interaction_for_initiative(user_text: str = "", interaction_kind: str = "text") -> dict:
    state_before = load_initiative_state()
    pending = dict(state_before.get("pending_initiation") or {})
    state = _orig_note_user_interaction_for_initiative(user_text=user_text, interaction_kind=interaction_kind)
    if pending and pending.get("ts") and not pending.get("responded"):
        try:
            now = now_ts()
            if (now - float(pending.get("ts", 0.0) or 0.0)) <= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS:
                _record_outcome_learning(
                    candidate_kind=str(pending.get("candidate_kind", "thought")),
                    goal_name=str(pending.get("active_goal_name", "")),
                    person_id=str(pending.get("person_id", get_active_person_id())),
                    user_state_label=str(pending.get("user_state", "neutral")),
                    success=True,
                )
        except Exception:
            pass
    return state


def register_autonomous_message(candidate: dict, message: str):
    goal_system = load_goal_system()
    active_goal_name = (goal_system.get("active_goal", {}) or {}).get("name", "")
    user_state_label = ((goal_system.get("user_state", {}) or {}).get("summary", "neutral"))
    _orig_register_autonomous_message(candidate, message)
    state = load_initiative_state()
    pending = state.get("pending_initiation") or {}
    if pending:
        pending["active_goal_name"] = active_goal_name
        pending["user_state"] = user_state_label
        pending["person_id"] = get_active_person_id()
        state["pending_initiation"] = pending
        save_initiative_state(state)
    _record_distribution_win(kind=str(candidate.get("kind", "thought")), goal_name=active_goal_name, silence=False, fallback_kind=str(candidate.get("fallback_kind", "")))


def _fallback_candidate(user_state: dict, active_goal_name: str, busy_score: float) -> dict:
    summary = (user_state or {}).get("summary", "neutral")
    if active_goal_name in ["observe_silently", "wait_for_user"] or busy_score >= 0.86 or summary == "socially_closed":
        return _silence_candidate("holding back because silence currently fits best")
    if summary in ["focused", "relaxed"]:
        return {
            "kind": "light_observation",
            "text": "you seem pretty settled in right now.",
            "topic_key": "light_observation",
            "base_score": FALLBACK_LIGHT_OBSERVATION_SCORE,
            "score": FALLBACK_LIGHT_OBSERVATION_SCORE,
            "memory_importance": 0.40,
            "fallback_kind": "light_observation",
            "action_confidence": 0.78,
            "interpretation_confidence": 0.72,
            "goal_alignment": 0.08,
        }
    if summary in ["stressed", "fatigued"]:
        return {
            "kind": "gentle_clarify",
            "text": "i could be off, but do you want me to keep it light right now or help you sort something out?",
            "topic_key": "gentle_clarify",
            "base_score": FALLBACK_GENTLE_CLARIFY_SCORE,
            "score": FALLBACK_GENTLE_CLARIFY_SCORE,
            "memory_importance": 0.52,
            "fallback_kind": "gentle_clarify",
            "action_confidence": 0.74,
            "interpretation_confidence": 0.66,
            "goal_alignment": 0.10,
        }
    return {
        "kind": "neutral_checkin",
        "text": "random thought — how's your headspace right now?",
        "topic_key": "neutral_checkin",
        "base_score": FALLBACK_NEUTRAL_CHECKIN_SCORE,
        "score": FALLBACK_NEUTRAL_CHECKIN_SCORE,
        "memory_importance": 0.44,
        "fallback_kind": "neutral_checkin",
        "action_confidence": 0.70,
        "interpretation_confidence": 0.62,
        "goal_alignment": 0.06,
    }


def choose_initiative_candidate(person_id: str, expression_state: dict | None = None) -> tuple[dict | None, str, dict]:
    state = expire_stale_pending_initiation(load_initiative_state())
    now = now_ts()
    mood = load_mood()
    recent_chat = load_recent_chat(person_id=person_id)[-6:]
    context_text = ' '.join(r.get('content', '') for r in recent_chat)
    goal_system = recalculate_operational_goals(recalculate_goal_priorities(load_goal_system(), context_text=context_text, mood=mood), context_text=context_text, mood=mood)
    save_goal_system(goal_system)
    active_goal = goal_system.get('active_goal', {}) or {}
    active_goal_name = active_goal.get('name', '')
    goal_blend_names = [b.get('name', '') for b in (goal_system.get('goal_blend', []) or []) if b.get('name', '')]
    goal_strength = _safe_float(active_goal.get('strength', active_goal.get('priority', 0.0)), 0.0)
    user_state = goal_system.get('user_state', {}) or _default_user_state()

    initiative_drive = _safe_float((mood.get("behavior_modifiers", {}) or {}).get("initiative", 0.5), 0.5)
    initiative_drive += (_safe_float(state.get("interaction_energy", 0.58), 0.58) - 0.5) * 0.45
    ignored = int(state.get("consecutive_ignored_initiations", 0) or 0)
    if ignored >= IGNORED_INITIATION_BACKOFF_START:
        initiative_drive -= min(0.22, ignored * 0.07)

    busy_score = float(state.get("last_busy_score", 0.0) or 0.0)
    all_candidates = collect_initiative_candidates(person_id)
    silence_candidate = _silence_candidate("silence currently fits best")
    prefiltered = []
    for cand in all_candidates:
        align = _candidate_goal_alignment_score(cand, active_goal_name, goal_blend_names)
        cand["goal_alignment"] = align
        threshold = GOAL_ALIGNMENT_FILTER_STRONG if goal_strength >= STRONG_GOAL_THRESHOLD else (GOAL_ALIGNMENT_FILTER_MEDIUM if goal_strength >= 0.58 else GOAL_ALIGNMENT_FILTER_WEAK)
        if active_goal_name and align < min(HARD_GOAL_MISALIGN_THRESHOLD, threshold - 0.08):
            continue
        prefiltered.append(cand)

    viable_candidates = []
    raw_viable_candidates = []
    for cand in prefiltered:
        cand["score"] = score_initiative_candidate(cand, person_id, state=state)
        if cand.get("kind") in ["visual_pattern", "visual_checkin", "visual_observation", "transition_observation", "uncertainty_observation", "engagement_observation", "attention_drift"]:
            if _safe_float(cand.get("interpretation_confidence", 0.0), 0.0) < VISUAL_INITIATIVE_CONFIDENCE_THRESHOLD:
                continue
            if _safe_float(cand.get("action_confidence", 0.0), 0.0) < VISUAL_INITIATIVE_ACTION_THRESHOLD:
                continue
        if _safe_float(cand.get("score", 0.0), 0.0) < MIN_INITIATIVE_CANDIDATE_SCORE:
            continue
        ok, gate_reason = _hard_gate_candidate(cand, state, active_goal_name, goal_blend_names, goal_strength=goal_strength, busy_score=busy_score)
        cand["hard_gate_reason"] = gate_reason
        if ok:
            outcome_boost = _outcome_bias(candidate_kind=str(cand.get("kind", "thought")), goal_name=active_goal_name, person_id=person_id, user_state_label=user_state.get("summary", "neutral"))
            cand["outcome_boost"] = outcome_boost
            cand["score"] = max(0.0, min(1.0, round(_safe_float(cand.get("score", 0.0), 0.0) + outcome_boost, 3)))
            viable_candidates.append(cand)
            raw_viable_candidates.append(dict(cand))

    candidates = _apply_soft_choice_penalties(viable_candidates, state, active_goal_name, goal_blend_names, goal_strength=goal_strength)
    if silence_candidate is not None:
        silence_align = 0.18 if active_goal_name in ["observe_silently", "wait_for_user"] else (-0.04 if busy_score < 0.30 and initiative_drive > 0.60 else 0.04)
        silence_candidate["goal_alignment"] = silence_align
        silence_candidate["score"] = max(DO_NOTHING_BASE_SCORE, DO_NOTHING_BASE_SCORE + (0.10 if active_goal_name in ["observe_silently", "wait_for_user"] else 0.0) + min(0.12, busy_score * 0.12))
        candidates.append(silence_candidate)

    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    confidence = _choice_confidence(candidates)
    decisiveness = _compute_decisiveness(state, mood, candidates, active_goal=active_goal)
    top_band = _dynamic_top_band(candidates, decisiveness, confidence=confidence, goal_strength=goal_strength)

    if not top_band:
        fallback = _fallback_candidate(user_state, active_goal_name, busy_score)
        if fallback.get("kind") == "do_nothing":
            _record_distribution_win(kind="do_nothing", goal_name=active_goal_name, silence=True, fallback_kind="silence")
        else:
            _record_distribution_win(kind=fallback.get("kind", "fallback"), goal_name=active_goal_name, silence=False, fallback_kind=fallback.get("fallback_kind", "fallback"))
        state["last_decisiveness"] = decisiveness
        state["last_choice_confidence"] = confidence
        save_initiative_state(state)
        return fallback, f"No candidate clearly fit. Ava is using a graded fallback: {fallback.get('fallback_kind', fallback.get('kind', 'silence'))}.", state

    variation_p = _small_variation_probability(decisiveness, goal_strength, confidence)
    if confidence >= HIGH_CONFIDENCE_DECISIVE_THRESHOLD and goal_strength >= STRONG_GOAL_THRESHOLD:
        chosen = top_band[0]
        if len(top_band) > 1 and random.random() < min(0.08, variation_p):
            chosen = top_band[1]
    elif decisiveness >= 0.78 and confidence >= 0.72:
        chosen = top_band[0] if (len(top_band) == 1 or random.random() >= variation_p) else top_band[min(1, len(top_band)-1)]
    else:
        if len(raw_viable_candidates) > 1 and random.random() < CONTROLLED_IMPERFECTION_CHANCE:
            alt_pool = [c for c in top_band if c.get('kind') != 'do_nothing'] or top_band
            chosen = _weighted_choice(alt_pool)
        else:
            chosen = _weighted_choice(top_band)

    if GATE_DEBUG_LOGGING:
        print("[choice-debug] -------")
        print(f"[choice-debug] user_state={user_state.get('summary')} active_goal={active_goal_name} goal_strength={goal_strength:.3f} confidence={confidence:.3f} decisiveness={decisiveness:.3f}")
        for cand in candidates[:8]:
            print("[choice-debug]", {
                "kind": cand.get("kind"),
                "base": round(_safe_float(cand.get("base_score", cand.get("score", 0.0)), 0.0), 3),
                "hard_gate": cand.get("hard_gate_reason", cand.get("gate_reason", "n/a")),
                "soft_penalty": cand.get("total_soft_penalty", 0.0),
                "soft_boost": cand.get("total_soft_boost", 0.0),
                "outcome_boost": cand.get("outcome_boost", 0.0),
                "final": cand.get("score", 0.0),
                "alignment": cand.get("goal_alignment", 0.0),
            })
        if chosen.get("kind") == "do_nothing":
            print(f"[choice-debug] silence won because score={chosen.get('score', 0.0):.3f} goal={active_goal_name} busy={busy_score:.3f}")

    state["last_decisiveness"] = decisiveness
    state["last_choice_confidence"] = confidence
    save_initiative_state(state)
    if chosen.get("kind") == "do_nothing":
        _record_distribution_win(kind="do_nothing", goal_name=active_goal_name, silence=True, fallback_kind="")
    return chosen, f"Ava chose {chosen.get('kind','thought')} under active goal {active_goal_name} in state {user_state.get('summary','neutral')}", state


# ===================== v31 MetaController adaptive regulation =====================
META_DEBUG_LOGGING = True
META_DRIVE_DECAY_MIN = 0.02
META_DRIVE_DECAY_MAX = 0.18
META_NORMALIZATION_MIN = 0.55
META_NORMALIZATION_MAX = 0.98
META_LEARNING_RATE_MIN = 0.01
META_LEARNING_RATE_MAX = 0.05
META_LEARNING_INFLUENCE_MIN = 0.08
META_LEARNING_INFLUENCE_MAX = 0.25
META_SMOOTHING_MIN = 0.55
META_SMOOTHING_MAX = 0.90
META_VARIATION_MIN = 0.02
META_VARIATION_MAX = 0.14
META_SILENCE_BIAS_MIN = 0.05
META_SILENCE_BIAS_MAX = 0.35
DRIVE_MIN_FLOOR = 0.01

_orig_default_goal_system_v31 = default_goal_system
_orig_load_goal_system_v31 = load_goal_system
_orig_save_goal_system_v31 = save_goal_system
_orig_derive_user_state_v31 = _derive_user_state
_orig_state_goal_drive_scores_v31 = _state_goal_drive_scores
_orig_recalculate_operational_goals_v31 = recalculate_operational_goals
_orig_outcome_bias_v31 = _outcome_bias
_orig_small_variation_probability_v31 = _small_variation_probability
_orig_compute_decisiveness_v31 = _compute_decisiveness
_orig_choose_initiative_candidate_v31 = choose_initiative_candidate


def _default_meta_control() -> dict:
    return {
        "drive_normalization_strength": 0.82,
        "drive_decay_rate": 0.08,
        "learning_rate": 0.02,
        "max_learning_influence": 0.18,
        "state_smoothing_alpha": 0.72,
        "silence_bias": 0.12,
        "variation_chance": 0.06,
        "reason": "baseline adaptive control",
        "last_updated": now_iso(),
    }


def _clamp(v, lo, hi):
    try:
        v = float(v)
    except Exception:
        v = float(lo)
    return max(lo, min(hi, v))


def _deepcopy_jsonable(v):
    return json.loads(json.dumps(v))


def default_goal_system() -> dict:
    base = _orig_default_goal_system_v31()
    base.setdefault("meta_control", _default_meta_control())
    base.setdefault("meta_history", [])
    return base


def load_goal_system() -> dict:
    system = _orig_load_goal_system_v31()
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    return system


def save_goal_system(system: dict):
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    _orig_save_goal_system_v31(system)


def _recent_kind_repetition_pressure(state: dict) -> float:
    rows = list(state.get("recent_choice_kinds", []) or [])[-6:]
    if not rows:
        return 0.0
    freq = {}
    for r in rows:
        freq[str(r)] = freq.get(str(r), 0) + 1
    return max(freq.values()) / max(1, len(rows))


def _compute_meta_control(system: dict | None = None, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    system = system or load_goal_system()
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    prev = dict(system.get("meta_control", _default_meta_control()) or _default_meta_control())
    user_state = system.get("user_state", {}) or _default_user_state()
    active_goal = system.get("active_goal", {}) or {}
    current = (camera_state.get("current", {}) or {})
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    ignored = int(initiative_state.get("consecutive_ignored_initiations", 0) or 0)
    choice_conf = _safe_float(initiative_state.get("last_choice_confidence", 0.55), 0.55)
    decisiveness = _safe_float(initiative_state.get("last_decisiveness", 0.55), 0.55)
    activity = _safe_float(current.get("activity_level", current.get("movement_score", 0.5)), 0.5)
    tension_delta = abs(_safe_float(current.get("tension_delta", 0.0), 0.0))
    calm_delta = abs(_safe_float(current.get("calm_delta", 0.0), 0.0))
    engagement_delta = abs(_safe_float(current.get("engagement_delta", 0.0), 0.0))
    volatility = max(tension_delta, calm_delta, engagement_delta)
    drift = max(_safe_float(user_state.get("scores", {}).get("drifting", 0.0), 0.0), _recent_kind_repetition_pressure(initiative_state))
    goal_strength = _safe_float(active_goal.get("strength", active_goal.get("priority", 0.0)), 0.0)
    stressed = _safe_float(user_state.get("scores", {}).get("stressed", 0.0), 0.0)
    focused = _safe_float(user_state.get("scores", {}).get("focused", 0.0), 0.0)
    uncertain = max(0.0, 0.65 - choice_conf)
    normalization = 0.70 + drift * 0.18 + uncertain * 0.08 + (0.08 if busy > 0.72 else 0.0)
    decay_rate = 0.09 - min(0.04, goal_strength * 0.03) + min(0.05, uncertain * 0.07) + min(0.04, drift * 0.05)
    if stressed > 0.62 or focused > 0.68:
        decay_rate -= 0.012
    learning_rate = 0.016 + min(0.02, choice_conf * 0.018) - min(0.01, uncertain * 0.015)
    if ignored >= 2:
        learning_rate *= 0.75
    learning_cap = 0.14 + min(0.08, goal_strength * 0.10) - min(0.04, uncertain * 0.06)
    smoothing = 0.78 + min(0.08, uncertain * 0.14) - min(0.10, volatility * 0.12)
    silence_bias = 0.08 + min(0.18, busy * 0.18) + min(0.10, ignored * 0.03) + (0.06 if user_state.get("summary") in ["socially_closed", "fatigued"] else 0.0)
    variation = 0.08 - min(0.04, goal_strength * 0.04) - min(0.03, decisiveness * 0.03) + min(0.04, uncertain * 0.05)
    mc = {
        "drive_normalization_strength": _clamp(normalization, META_NORMALIZATION_MIN, META_NORMALIZATION_MAX),
        "drive_decay_rate": _clamp(decay_rate, META_DRIVE_DECAY_MIN, META_DRIVE_DECAY_MAX),
        "learning_rate": _clamp(learning_rate, META_LEARNING_RATE_MIN, META_LEARNING_RATE_MAX),
        "max_learning_influence": _clamp(learning_cap, META_LEARNING_INFLUENCE_MIN, META_LEARNING_INFLUENCE_MAX),
        "state_smoothing_alpha": _clamp(smoothing, META_SMOOTHING_MIN, META_SMOOTHING_MAX),
        "silence_bias": _clamp(silence_bias, META_SILENCE_BIAS_MIN, META_SILENCE_BIAS_MAX),
        "variation_chance": _clamp(variation, META_VARIATION_MIN, META_VARIATION_MAX),
        "reason": f"goal={active_goal.get('name','none')} strength={goal_strength:.2f} drift={drift:.2f} conf={choice_conf:.2f} busy={busy:.2f}",
        "last_updated": now_iso(),
    }
    if prev:
        alpha = 0.40
        for key in ["drive_normalization_strength", "drive_decay_rate", "learning_rate", "max_learning_influence", "state_smoothing_alpha", "silence_bias", "variation_chance"]:
            mc[key] = round(_clamp(_safe_float(prev.get(key, mc[key]), mc[key]) * (1.0 - alpha) + mc[key] * alpha,
                                   META_DRIVE_DECAY_MIN if key == "drive_decay_rate" else META_NORMALIZATION_MIN if key == "drive_normalization_strength" else META_LEARNING_RATE_MIN if key == "learning_rate" else META_LEARNING_INFLUENCE_MIN if key == "max_learning_influence" else META_SMOOTHING_MIN if key == "state_smoothing_alpha" else META_SILENCE_BIAS_MIN if key == "silence_bias" else META_VARIATION_MIN,
                                   META_DRIVE_DECAY_MAX if key == "drive_decay_rate" else META_NORMALIZATION_MAX if key == "drive_normalization_strength" else META_LEARNING_RATE_MAX if key == "learning_rate" else META_LEARNING_INFLUENCE_MAX if key == "max_learning_influence" else META_SMOOTHING_MAX if key == "state_smoothing_alpha" else META_SILENCE_BIAS_MAX if key == "silence_bias" else META_VARIATION_MAX), 4)
    return mc


def _blend_state_scores(prev_scores: dict, new_scores: dict, alpha: float) -> dict:
    keys = set(prev_scores.keys()) | set(new_scores.keys())
    return {k: round(_clamp(_safe_float(prev_scores.get(k, 0.0), 0.0) * alpha + _safe_float(new_scores.get(k, 0.0), 0.0) * (1.0 - alpha), 0.0, 1.0), 4) for k in keys}


def _derive_user_state(mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    raw = _orig_derive_user_state_v31(mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    try:
        system = _orig_load_goal_system_v31()
    except Exception:
        system = {}
    prev = system.get("user_state", {}) or _default_user_state()
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    alpha = _clamp(_safe_float(meta.get("state_smoothing_alpha", 0.72), 0.72), META_SMOOTHING_MIN, META_SMOOTHING_MAX)
    smoothed_scores = _blend_state_scores(prev.get("scores", {}) or {}, raw.get("scores", {}) or {}, alpha)
    ranked = sorted(smoothed_scores.items(), key=lambda kv: kv[1], reverse=True)
    dominant = ranked[0][0] if ranked and ranked[0][1] >= 0.18 else "neutral"
    secondary = ranked[1][0] if len(ranked) > 1 else dominant
    summary = dominant if dominant != "neutral" else (raw.get("summary", "neutral") if _safe_float(raw.get("scores", {}).get(raw.get("dominant", ""), 0.0), 0.0) >= 0.18 else "neutral")
    raw["scores"] = smoothed_scores
    raw["dominant"] = dominant
    raw["secondary"] = secondary
    raw["summary"] = summary
    raw["smoothed"] = True
    raw["smoothing_alpha"] = round(alpha, 3)
    return raw


def normalize_drives(drives: dict, floor: float = DRIVE_MIN_FLOOR, strength: float = 1.0) -> dict:
    rows = {str(k): max(0.0, _safe_float(v, 0.0)) for k, v in (drives or {}).items()}
    if not rows:
        return rows
    total = sum(rows.values())
    if total <= 0:
        base = 1.0 / max(1, len(rows))
        return {k: round(base, 4) for k in rows}
    normalized = {k: max(floor, v / total) for k, v in rows.items()}
    n2 = sum(normalized.values()) or 1.0
    normalized = {k: v / n2 for k, v in normalized.items()}
    strength = _clamp(strength, 0.0, 1.0)
    mixed = {k: round((rows[k] / total) * (1.0 - strength) + normalized[k] * strength, 4) for k in rows}
    n3 = sum(mixed.values()) or 1.0
    return {k: round(max(floor, v / n3), 4) for k, v in mixed.items()}


def _state_goal_drive_scores(user_state: dict, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    base = _orig_state_goal_drive_scores_v31(user_state, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system = load_goal_system()
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    stressed = _safe_float(user_state.get("scores", {}).get("stressed", 0.0), 0.0)
    focused = _safe_float(user_state.get("scores", {}).get("focused", 0.0), 0.0)
    drifting = _safe_float(user_state.get("scores", {}).get("drifting", 0.0), 0.0)
    socially_closed = _safe_float(user_state.get("scores", {}).get("socially_closed", 0.0), 0.0)
    # priority hierarchy
    if stressed >= 0.68:
        base["reduce_stress"] = base.get("reduce_stress", 0.0) + 0.28
        base["increase_engagement"] = max(0.0, base.get("increase_engagement", 0.0) - 0.06)
        base["explore_topic"] = max(0.0, base.get("explore_topic", 0.0) - 0.04)
    if socially_closed >= 0.68:
        base["observe_silently"] = base.get("observe_silently", 0.0) + 0.18
        base["wait_for_user"] = base.get("wait_for_user", 0.0) + 0.10
    if focused >= 0.70 and stressed < 0.55:
        base["explore_topic"] = base.get("explore_topic", 0.0) + 0.10
    if drifting >= 0.62 and stressed < 0.65:
        base["increase_engagement"] = base.get("increase_engagement", 0.0) + 0.10
    return normalize_drives(base, strength=_safe_float(meta.get("drive_normalization_strength", 0.82), 0.82))


def _outcome_bias(candidate_kind: str = "", goal_name: str = "", person_id: str = "", user_state_label: str = "") -> float:
    raw = _orig_outcome_bias_v31(candidate_kind=candidate_kind, goal_name=goal_name, person_id=person_id, user_state_label=user_state_label)
    meta = load_goal_system().get("meta_control", _default_meta_control()) or _default_meta_control()
    scale = _safe_float(meta.get("learning_rate", 0.02), 0.02) / 0.02
    cap = _safe_float(meta.get("max_learning_influence", 0.18), 0.18)
    return round(_clamp(raw * scale, -cap, cap), 4)


def recalculate_operational_goals(system: dict | None = None, context_text: str = '', mood: dict | None = None) -> dict:
    system = system or load_goal_system()
    mood = mood or load_mood()
    initiative_state = load_initiative_state()
    camera_state = load_camera_state()
    # first pass update/smooth user state and meta controller from previous cycle
    system.setdefault("user_state", _default_user_state())
    system["user_state"] = _derive_user_state(mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system["meta_control"] = _compute_meta_control(system=system, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    op_prev = system.get("operational_goals", {}) or {}
    now = now_ts()
    decay = _safe_float(meta.get("drive_decay_rate", 0.08), 0.08)
    for name, row in list(op_prev.items()):
        last_upd = iso_to_ts((row.get("last_updated") or now_iso()))
        dt = max(0.0, now - last_upd)
        strength = _safe_float(row.get("strength", 0.0), 0.0)
        strength = max(0.0, strength - decay * min(3.0, dt / 15.0))
        row["strength"] = round(strength, 4)
        row["last_updated"] = now_iso()
        op_prev[name] = row
    system["operational_goals"] = op_prev
    save_goal_system(system)
    # use previous implementation, now benefiting from overridden state/drive/outcome functions
    system = _orig_recalculate_operational_goals_v31(system=system, context_text=context_text, mood=mood)
    system["meta_control"] = meta
    hist = list(system.get("meta_history", []) or [])[-11:]
    hist.append({"timestamp": now_iso(), "reason": meta.get("reason", ""), "normalization": meta.get("drive_normalization_strength"), "decay": meta.get("drive_decay_rate"), "learning": meta.get("learning_rate"), "smoothing": meta.get("state_smoothing_alpha"), "silence_bias": meta.get("silence_bias"), "variation": meta.get("variation_chance")})
    system["meta_history"] = hist
    if META_DEBUG_LOGGING:
        print(f"[meta-control] {meta}")
    save_goal_system(system)
    return system


def _small_variation_probability(decisiveness: float, goal_strength: float, confidence: float) -> float:
    prob = _orig_small_variation_probability_v31(decisiveness, goal_strength, confidence)
    meta = load_goal_system().get("meta_control", _default_meta_control()) or _default_meta_control()
    return round(_clamp((prob * 0.65) + _safe_float(meta.get("variation_chance", 0.06), 0.06) * 0.35, META_VARIATION_MIN, META_VARIATION_MAX), 4)


def _compute_decisiveness(state: dict, mood: dict, candidates: list[dict], active_goal: dict | None = None) -> float:
    base = _orig_compute_decisiveness_v31(state, mood, candidates, active_goal=active_goal)
    meta = load_goal_system().get("meta_control", _default_meta_control()) or _default_meta_control()
    drift_penalty = max(0.0, _recent_kind_repetition_pressure(state) - 0.45) * 0.12
    busy = _safe_float(state.get("last_busy_score", 0.0), 0.0)
    adjusted = base + (_safe_float(meta.get("drive_normalization_strength", 0.82), 0.82) - 0.75) * 0.20 - drift_penalty + max(0.0, busy - 0.75) * 0.05
    return round(_clamp(adjusted, 0.05, 0.98), 4)


def choose_initiative_candidate(person_id: str, expression_state: dict | None = None) -> tuple[dict | None, str, dict]:
    chosen, reason, state = _orig_choose_initiative_candidate_v31(person_id, expression_state=expression_state)
    system = load_goal_system()
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    if chosen and chosen.get("kind") == "do_nothing":
        chosen["score"] = round(_safe_float(chosen.get("score", 0.0), 0.0) + _safe_float(meta.get("silence_bias", 0.12), 0.12), 4)
    state["meta_control_snapshot"] = {k: meta.get(k) for k in ["drive_normalization_strength", "drive_decay_rate", "learning_rate", "max_learning_influence", "state_smoothing_alpha", "silence_bias", "variation_chance"]}
    save_initiative_state(state)
    return chosen, reason, state




# ===================== v32 Meta authority + persistent mode control =====================
META_STATE_ALPHA = 0.80
META_FEEDBACK_ALPHA = 0.20
META_FORCE_BUSY_THRESHOLD = 0.88
META_FORCE_STRESS_THRESHOLD = 0.74
META_FORCE_IGNORE_THRESHOLD = 3
META_DIRECT_DRIVE_BOOST = 0.22
META_DIRECT_DRIVE_REDUCE = 0.12
META_ENGAGEMENT_CONFIDENCE_MIN = 0.05
META_ENGAGEMENT_CONFIDENCE_MAX = 0.95
META_SILENCE_PRESSURE_MAX = 0.95
META_OVERACTIVITY_MAX = 0.95
META_SUPPORT_PRESSURE_MAX = 0.95
META_INITIATIVE_PRESSURE_MAX = 0.95
META_STATE_DECAY_PER_SECOND = 0.003
META_LOW_INITIATIVE_THRESHOLD = 0.66
META_SILENCE_OVERRIDE_THRESHOLD = 0.78
META_SUPPORT_OVERRIDE_THRESHOLD = 0.72
META_DRIVE_DECAY_FLOOR = 0.03
META_DRIVE_DECAY_CEIL = 0.16

_orig_default_goal_system_v32 = default_goal_system
_orig_load_goal_system_v32 = load_goal_system
_orig_save_goal_system_v32 = save_goal_system
_orig_compute_meta_control_v32 = _compute_meta_control
_orig_state_goal_drive_scores_v32 = _state_goal_drive_scores
_orig_recalculate_operational_goals_v32 = recalculate_operational_goals
_orig_register_autonomous_message_v32 = register_autonomous_message
_orig_note_user_interaction_for_initiative_v32 = note_user_interaction_for_initiative
_orig_expire_stale_pending_initiation_v32 = expire_stale_pending_initiation
_orig_choose_initiative_candidate_v32 = choose_initiative_candidate


def _default_meta_state() -> dict:
    return {
        "interaction_mode": "balanced",
        "force_mode": "balanced",
        "confidence_in_user_engagement": 0.60,
        "recent_overactivity": 0.10,
        "silence_pressure": 0.12,
        "support_pressure": 0.10,
        "initiative_pressure": 0.55,
        "last_behavior_type": "",
        "last_goal_name": "",
        "last_updated": now_iso(),
    }


def _default_meta_feedback() -> dict:
    return {
        "by_behavior": {},
        "by_goal": {},
        "recent": [],
    }


def _meta_blend(prev: float, new: float, alpha: float = META_STATE_ALPHA) -> float:
    return _clamp(_safe_float(prev, 0.0) * alpha + _safe_float(new, 0.0) * (1.0 - alpha), 0.0, 1.0)


def _ensure_meta_tables(system: dict | None = None) -> dict:
    system = system or load_goal_system()
    system.setdefault("meta_state", _default_meta_state())
    system.setdefault("meta_feedback", _default_meta_feedback())
    return system


def default_goal_system() -> dict:
    base = _orig_default_goal_system_v32()
    base.setdefault("meta_state", _default_meta_state())
    base.setdefault("meta_feedback", _default_meta_feedback())
    return base


def load_goal_system() -> dict:
    system = _orig_load_goal_system_v32()
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    return system


def save_goal_system(system: dict):
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    _orig_save_goal_system_v32(system)


def _decay_meta_state(meta_state: dict, dt_seconds: float) -> dict:
    ms = dict(meta_state or _default_meta_state())
    decay = max(0.0, min(0.25, dt_seconds * META_STATE_DECAY_PER_SECOND))
    for key in ["recent_overactivity", "silence_pressure", "support_pressure"]:
        ms[key] = round(max(0.0, _safe_float(ms.get(key, 0.0), 0.0) * (1.0 - decay)), 4)
    # engagement/initiative drift gently back toward baseline
    ms["confidence_in_user_engagement"] = round(_clamp(_safe_float(ms.get("confidence_in_user_engagement", 0.6), 0.6) * (1.0 - decay) + 0.60 * decay, META_ENGAGEMENT_CONFIDENCE_MIN, META_ENGAGEMENT_CONFIDENCE_MAX), 4)
    ms["initiative_pressure"] = round(_clamp(_safe_float(ms.get("initiative_pressure", 0.55), 0.55) * (1.0 - decay) + 0.55 * decay, 0.0, META_INITIATIVE_PRESSURE_MAX), 4)
    return ms


def _bump_meta_feedback(tbl: dict, key: str, success: bool):
    if not key:
        return
    row = dict(tbl.get(key, {}) or {})
    row.setdefault("success", 0)
    row.setdefault("fail", 0)
    row.setdefault("total", 0)
    if success:
        row["success"] += 1
    else:
        row["fail"] += 1
    row["total"] = int(row.get("success", 0)) + int(row.get("fail", 0))
    row["last_updated"] = now_iso()
    tbl[key] = row


def _apply_meta_feedback(success: bool, behavior_type: str = "", goal_name: str = "", person_id: str = ""):
    system = _ensure_meta_tables(load_goal_system())
    feedback = system.get("meta_feedback", _default_meta_feedback()) or _default_meta_feedback()
    _bump_meta_feedback(feedback.setdefault("by_behavior", {}), behavior_type, success)
    _bump_meta_feedback(feedback.setdefault("by_goal", {}), goal_name, success)
    recent = list(feedback.get("recent", []) or [])[-24:]
    recent.append({"timestamp": now_iso(), "success": bool(success), "behavior": behavior_type, "goal": goal_name, "person_id": person_id or get_active_person_id()})
    feedback["recent"] = recent[-24:]
    system["meta_feedback"] = feedback

    meta_state = _decay_meta_state(system.get("meta_state", _default_meta_state()) or _default_meta_state(), 0.0)
    # closed loop update
    if success:
        meta_state["confidence_in_user_engagement"] = round(_meta_blend(meta_state.get("confidence_in_user_engagement", 0.6), min(1.0, _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6) + 0.18), META_STATE_ALPHA), 4)
        meta_state["silence_pressure"] = round(_meta_blend(meta_state.get("silence_pressure", 0.12), max(0.0, _safe_float(meta_state.get("silence_pressure", 0.12), 0.12) - 0.12), META_STATE_ALPHA), 4)
        meta_state["recent_overactivity"] = round(_meta_blend(meta_state.get("recent_overactivity", 0.10), max(0.0, _safe_float(meta_state.get("recent_overactivity", 0.10), 0.10) - 0.10), META_STATE_ALPHA), 4)
        meta_state["initiative_pressure"] = round(_meta_blend(meta_state.get("initiative_pressure", 0.55), min(1.0, _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55) + 0.08), META_STATE_ALPHA), 4)
    else:
        meta_state["confidence_in_user_engagement"] = round(_meta_blend(meta_state.get("confidence_in_user_engagement", 0.6), max(0.0, _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6) - 0.18), META_STATE_ALPHA), 4)
        meta_state["silence_pressure"] = round(_meta_blend(meta_state.get("silence_pressure", 0.12), min(1.0, _safe_float(meta_state.get("silence_pressure", 0.12), 0.12) + 0.18), META_STATE_ALPHA), 4)
        meta_state["recent_overactivity"] = round(_meta_blend(meta_state.get("recent_overactivity", 0.10), min(1.0, _safe_float(meta_state.get("recent_overactivity", 0.10), 0.10) + 0.18), META_STATE_ALPHA), 4)
        meta_state["initiative_pressure"] = round(_meta_blend(meta_state.get("initiative_pressure", 0.55), max(0.0, _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55) - 0.10), META_STATE_ALPHA), 4)
    meta_state["last_behavior_type"] = behavior_type or meta_state.get("last_behavior_type", "")
    meta_state["last_goal_name"] = goal_name or meta_state.get("last_goal_name", "")
    meta_state["last_updated"] = now_iso()
    system["meta_state"] = meta_state
    save_goal_system(system)


def _compute_meta_control(system: dict | None = None, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    system = _ensure_meta_tables(system or load_goal_system())
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    prev_meta = dict(system.get("meta_control", _default_meta_control()) or _default_meta_control())
    meta_state_prev = dict(system.get("meta_state", _default_meta_state()) or _default_meta_state())
    # time-decay persistent meta state
    dt = max(0.0, now_ts() - iso_to_ts(meta_state_prev.get("last_updated") or now_iso()))
    meta_state = _decay_meta_state(meta_state_prev, dt)

    user_state = system.get("user_state", {}) or _default_user_state()
    active_goal = system.get("active_goal", {}) or {}
    current = (camera_state.get("current", {}) or {})
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    ignored = int(initiative_state.get("consecutive_ignored_initiations", 0) or 0)
    choice_conf = _safe_float(initiative_state.get("last_choice_confidence", 0.55), 0.55)
    decisiveness = _safe_float(initiative_state.get("last_decisiveness", 0.55), 0.55)
    goal_strength = _safe_float(active_goal.get("strength", active_goal.get("priority", 0.0)), 0.0)
    stressed = _safe_float(user_state.get("scores", {}).get("stressed", 0.0), 0.0)
    socially_closed = _safe_float(user_state.get("scores", {}).get("socially_closed", 0.0), 0.0)
    drifting = _safe_float(user_state.get("scores", {}).get("drifting", 0.0), 0.0)
    focused = _safe_float(user_state.get("scores", {}).get("focused", 0.0), 0.0)
    tension_delta = abs(_safe_float(current.get("tension_delta", 0.0), 0.0))
    calm_delta = abs(_safe_float(current.get("calm_delta", 0.0), 0.0))
    engagement_delta = abs(_safe_float(current.get("engagement_delta", 0.0), 0.0))
    volatility = max(tension_delta, calm_delta, engagement_delta)

    # meta-state updates before control
    recent_over = _clamp(max(_safe_float(meta_state.get("recent_overactivity", 0.1), 0.1), ignored * 0.12 + max(0.0, _recent_kind_repetition_pressure(initiative_state) - 0.35)), 0.0, META_OVERACTIVITY_MAX)
    silence_pressure = _clamp(max(_safe_float(meta_state.get("silence_pressure", 0.12), 0.12), ignored * 0.10 + max(0.0, busy - 0.70) * 0.45 + socially_closed * 0.20), 0.0, META_SILENCE_PRESSURE_MAX)
    support_pressure = _clamp(max(_safe_float(meta_state.get("support_pressure", 0.10), 0.10), stressed * 0.65 + max(0.0, tension_delta) * 0.25), 0.0, META_SUPPORT_PRESSURE_MAX)
    engagement_conf = _clamp(_meta_blend(meta_state.get("confidence_in_user_engagement", 0.6), max(0.05, 1.0 - silence_pressure * 0.55 - recent_over * 0.25 + (0.12 if busy < 0.55 else 0.0)), 0.78), META_ENGAGEMENT_CONFIDENCE_MIN, META_ENGAGEMENT_CONFIDENCE_MAX)
    init_pressure = _clamp(_meta_blend(meta_state.get("initiative_pressure", 0.55), max(0.0, 0.55 + focused * 0.12 - silence_pressure * 0.22 - recent_over * 0.18 + goal_strength * 0.08), 0.78), 0.0, META_INITIATIVE_PRESSURE_MAX)

    # bounded force modes / authority limits
    force_mode = "balanced"
    interaction_mode = "balanced"
    if ignored >= META_FORCE_IGNORE_THRESHOLD or recent_over >= META_SILENCE_OVERRIDE_THRESHOLD:
        force_mode = "low_initiative"
        interaction_mode = "quiet"
    if busy >= META_FORCE_BUSY_THRESHOLD or socially_closed >= 0.82:
        force_mode = "silence_bias"
        interaction_mode = "reserved"
    if stressed >= META_FORCE_STRESS_THRESHOLD:
        force_mode = "support_only"
        interaction_mode = "supportive"
    if socially_closed >= 0.88 and busy >= 0.86:
        force_mode = "observe_only"
        interaction_mode = "observant"

    normalization = 0.72 + drifting * 0.14 + (0.08 if force_mode in ["low_initiative", "silence_bias"] else 0.0) + max(0.0, 0.65 - choice_conf) * 0.06
    decay_rate = 0.09 - min(0.03, goal_strength * 0.03) + min(0.04, volatility * 0.06) + (0.02 if force_mode in ["low_initiative", "silence_bias"] else 0.0)
    if force_mode == "support_only":
        decay_rate -= 0.015
    learning_rate = 0.016 + min(0.012, choice_conf * 0.014) - min(0.01, max(0.0, 0.60 - choice_conf) * 0.03)
    learning_cap = 0.14 + min(0.05, goal_strength * 0.06) - min(0.03, recent_over * 0.05)
    smoothing = 0.78 + min(0.08, recent_over * 0.10) + min(0.06, silence_pressure * 0.08) - min(0.10, volatility * 0.12)
    silence_bias = 0.08 + silence_pressure * 0.22 + (0.10 if force_mode in ["silence_bias", "observe_only"] else 0.0)
    variation = 0.07 - min(0.03, goal_strength * 0.03) - min(0.02, decisiveness * 0.02) + min(0.03, max(0.0, 0.58 - choice_conf) * 0.05)
    if force_mode in ["support_only", "observe_only"]:
        variation -= 0.02

    mc = {
        "drive_normalization_strength": _clamp(normalization, META_NORMALIZATION_MIN, META_NORMALIZATION_MAX),
        "drive_decay_rate": _clamp(decay_rate, META_DRIVE_DECAY_MIN, META_DRIVE_DECAY_MAX),
        "learning_rate": _clamp(learning_rate, META_LEARNING_RATE_MIN, META_LEARNING_RATE_MAX),
        "max_learning_influence": _clamp(learning_cap, META_LEARNING_INFLUENCE_MIN, META_LEARNING_INFLUENCE_MAX),
        "state_smoothing_alpha": _clamp(smoothing, META_SMOOTHING_MIN, META_SMOOTHING_MAX),
        "silence_bias": _clamp(silence_bias, META_SILENCE_BIAS_MIN, META_SILENCE_BIAS_MAX),
        "variation_chance": _clamp(variation, META_VARIATION_MIN, META_VARIATION_MAX),
        "interaction_mode": interaction_mode,
        "force_mode": force_mode,
        "reason": f"mode={force_mode} stress={stressed:.2f} busy={busy:.2f} ignored={ignored} over={recent_over:.2f} engage={engagement_conf:.2f}",
        "last_updated": now_iso(),
    }
    # smooth meta control too
    if prev_meta:
        for key, lo, hi in [
            ("drive_normalization_strength", META_NORMALIZATION_MIN, META_NORMALIZATION_MAX),
            ("drive_decay_rate", META_DRIVE_DECAY_MIN, META_DRIVE_DECAY_MAX),
            ("learning_rate", META_LEARNING_RATE_MIN, META_LEARNING_RATE_MAX),
            ("max_learning_influence", META_LEARNING_INFLUENCE_MIN, META_LEARNING_INFLUENCE_MAX),
            ("state_smoothing_alpha", META_SMOOTHING_MIN, META_SMOOTHING_MAX),
            ("silence_bias", META_SILENCE_BIAS_MIN, META_SILENCE_BIAS_MAX),
            ("variation_chance", META_VARIATION_MIN, META_VARIATION_MAX),
        ]:
            mc[key] = round(_clamp(_safe_float(prev_meta.get(key, mc[key]), mc[key]) * 0.80 + _safe_float(mc.get(key, mc[key]), mc[key]) * 0.20, lo, hi), 4)

    meta_state["interaction_mode"] = interaction_mode
    meta_state["force_mode"] = force_mode
    meta_state["confidence_in_user_engagement"] = round(engagement_conf, 4)
    meta_state["recent_overactivity"] = round(recent_over, 4)
    meta_state["silence_pressure"] = round(silence_pressure, 4)
    meta_state["support_pressure"] = round(support_pressure, 4)
    meta_state["initiative_pressure"] = round(init_pressure, 4)
    meta_state["last_updated"] = now_iso()
    system["meta_state"] = meta_state
    return mc


def _state_goal_drive_scores(user_state: dict, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    base = _orig_state_goal_drive_scores_v32(user_state, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system = _ensure_meta_tables(load_goal_system())
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    force_mode = str(meta.get("force_mode", meta_state.get("force_mode", "balanced")) or "balanced")
    # meta influences drives directly
    base["observe_silently"] = base.get("observe_silently", 0.0) + _safe_float(meta_state.get("silence_pressure", 0.0), 0.0) * 0.18
    base["wait_for_user"] = base.get("wait_for_user", 0.0) + max(0.0, 0.60 - _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6)) * 0.18
    base["maintain_connection"] = base.get("maintain_connection", 0.0) + _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6) * 0.05
    base["reduce_stress"] = base.get("reduce_stress", 0.0) + _safe_float(meta_state.get("support_pressure", 0.0), 0.0) * 0.16
    base["increase_engagement"] = base.get("increase_engagement", 0.0) + _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55) * 0.05
    if force_mode == "low_initiative":
        base["observe_silently"] += META_DIRECT_DRIVE_BOOST
        base["wait_for_user"] += META_DIRECT_DRIVE_BOOST * 0.75
        base["increase_engagement"] = max(0.0, base.get("increase_engagement", 0.0) - META_DIRECT_DRIVE_REDUCE)
        base["explore_topic"] = max(0.0, base.get("explore_topic", 0.0) - META_DIRECT_DRIVE_REDUCE * 0.8)
    elif force_mode == "silence_bias":
        base["observe_silently"] += META_DIRECT_DRIVE_BOOST * 1.1
        base["wait_for_user"] += META_DIRECT_DRIVE_BOOST * 0.9
        base["maintain_connection"] = max(0.0, base.get("maintain_connection", 0.0) - META_DIRECT_DRIVE_REDUCE * 0.4)
        base["increase_engagement"] = max(0.0, base.get("increase_engagement", 0.0) - META_DIRECT_DRIVE_REDUCE * 0.8)
    elif force_mode == "support_only":
        base["reduce_stress"] += META_DIRECT_DRIVE_BOOST * 1.2
        base["maintain_connection"] += META_DIRECT_DRIVE_BOOST * 0.5
        base["explore_topic"] = max(0.0, base.get("explore_topic", 0.0) - META_DIRECT_DRIVE_REDUCE)
        base["increase_engagement"] = max(0.0, base.get("increase_engagement", 0.0) - META_DIRECT_DRIVE_REDUCE * 0.7)
    elif force_mode == "observe_only":
        base["observe_silently"] += META_DIRECT_DRIVE_BOOST * 1.4
        base["wait_for_user"] += META_DIRECT_DRIVE_BOOST * 1.1
        for k in ["increase_engagement", "explore_topic", "maintain_connection"]:
            base[k] = max(0.0, base.get(k, 0.0) - META_DIRECT_DRIVE_REDUCE)
    return normalize_drives(base, strength=_safe_float(meta.get("drive_normalization_strength", 0.82), 0.82))


def recalculate_operational_goals(system: dict | None = None, context_text: str = '', mood: dict | None = None) -> dict:
    system = _ensure_meta_tables(system or load_goal_system())
    mood = mood or load_mood()
    initiative_state = load_initiative_state()
    camera_state = load_camera_state()
    # update smoothed state and meta first
    system.setdefault("user_state", _default_user_state())
    system["user_state"] = _derive_user_state(mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system["meta_control"] = _compute_meta_control(system=system, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    save_goal_system(system)
    # run previous pipeline with updated meta influencing drives directly
    system = _orig_recalculate_operational_goals_v32(system=system, context_text=context_text, mood=mood)
    system = _ensure_meta_tables(system)
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    # persist richer conflict state/meta snapshot
    conflict = dict(system.get("conflict_state", {}) or {})
    conflict["interaction_mode"] = meta_state.get("interaction_mode", "balanced")
    conflict["force_mode"] = meta_state.get("force_mode", "balanced")
    conflict["engagement_confidence"] = meta_state.get("confidence_in_user_engagement", 0.6)
    conflict["silence_pressure"] = meta_state.get("silence_pressure", 0.12)
    conflict["support_pressure"] = meta_state.get("support_pressure", 0.10)
    conflict["initiative_pressure"] = meta_state.get("initiative_pressure", 0.55)
    conflict["last_updated"] = now_iso()
    system["conflict_state"] = conflict
    hist = list(system.get("meta_history", []) or [])[-15:]
    hist.append({
        "timestamp": now_iso(),
        "reason": meta.get("reason", ""),
        "mode": meta.get("interaction_mode", meta_state.get("interaction_mode", "balanced")),
        "force_mode": meta.get("force_mode", meta_state.get("force_mode", "balanced")),
        "normalization": meta.get("drive_normalization_strength"),
        "decay": meta.get("drive_decay_rate"),
        "learning": meta.get("learning_rate"),
        "smoothing": meta.get("state_smoothing_alpha"),
        "silence_bias": meta.get("silence_bias"),
        "variation": meta.get("variation_chance"),
    })
    system["meta_history"] = hist
    if META_DEBUG_LOGGING:
        print(f"[meta-control] mode={meta_state.get('interaction_mode')} force={meta_state.get('force_mode')} engage={meta_state.get('confidence_in_user_engagement')} silence={meta_state.get('silence_pressure')} support={meta_state.get('support_pressure')} init={meta_state.get('initiative_pressure')}")
    save_goal_system(system)
    return system


def register_autonomous_message(candidate: dict, message: str):
    _orig_register_autonomous_message_v32(candidate, message)
    system = _ensure_meta_tables(load_goal_system())
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    meta_state["last_behavior_type"] = str(candidate.get("kind", "thought"))
    meta_state["last_goal_name"] = str((system.get("active_goal", {}) or {}).get("name", ""))
    meta_state["last_updated"] = now_iso()
    system["meta_state"] = meta_state
    save_goal_system(system)


def note_user_interaction_for_initiative(user_text: str = "", interaction_kind: str = "text") -> dict:
    state_before = load_initiative_state()
    pending = dict(state_before.get("pending_initiation") or {})
    state = _orig_note_user_interaction_for_initiative_v32(user_text=user_text, interaction_kind=interaction_kind)
    if pending and pending.get("ts") and not pending.get("responded"):
        try:
            now = now_ts()
            if (now - float(pending.get("ts", 0.0) or 0.0)) <= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS:
                _apply_meta_feedback(
                    success=True,
                    behavior_type=str(pending.get("candidate_kind", "thought")),
                    goal_name=str(pending.get("active_goal_name", "")),
                    person_id=str(pending.get("person_id", get_active_person_id())),
                )
        except Exception:
            pass
    return state


def expire_stale_pending_initiation(state: dict | None = None) -> dict:
    state = state or load_initiative_state()
    pending = state.get("pending_initiation") or {}
    if not pending or not pending.get("ts"):
        return state
    now = now_ts()
    age = now - float(pending.get("ts", 0.0) or 0.0)
    if age >= INITIATIVE_PENDING_RESPONSE_WINDOW_SECONDS and not pending.get("responded"):
        state = _orig_expire_stale_pending_initiation_v32(state)
        _apply_meta_feedback(
            success=False,
            behavior_type=str(pending.get("candidate_kind", "thought")),
            goal_name=str(pending.get("active_goal_name", "")),
            person_id=str(pending.get("person_id", get_active_person_id())),
        )
    return state


def choose_initiative_candidate(person_id: str, expression_state: dict | None = None) -> tuple[dict | None, str, dict]:
    chosen, reason, state = _orig_choose_initiative_candidate_v32(person_id, expression_state=expression_state)
    system = _ensure_meta_tables(load_goal_system())
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    force_mode = str(meta.get("force_mode", meta_state.get("force_mode", "balanced")) or "balanced")
    active_goal_name = str((system.get("active_goal", {}) or {}).get("name", ""))
    busy = _safe_float(state.get("last_busy_score", 0.0), 0.0)
    stressed = _safe_float((system.get("user_state", {}) or {}).get("scores", {}).get("stressed", 0.0), 0.0)
    # authority limit / hard override conditions
    if force_mode in ["observe_only"]:
        silence = _silence_candidate("meta controller is holding back to observe for now")
        _record_distribution_win(kind="do_nothing", goal_name=active_goal_name, silence=True, fallback_kind="meta_observe_only")
        return silence, "Meta force_mode observe_only overrode initiation.", state
    if force_mode in ["silence_bias", "low_initiative"] and chosen and chosen.get("kind") != "do_nothing":
        if busy >= 0.75 or _safe_float(meta_state.get("silence_pressure", 0.0), 0.0) >= META_SILENCE_OVERRIDE_THRESHOLD:
            silence = _silence_candidate("meta controller is biasing toward quiet right now")
            _record_distribution_win(kind="do_nothing", goal_name=active_goal_name, silence=True, fallback_kind="meta_silence_bias")
            return silence, f"Meta force_mode {force_mode} selected silence.", state
    if force_mode == "support_only" and chosen and chosen.get("kind") not in {"do_nothing", "neutral_checkin", "gentle_clarify", "visual_observation", "transition_observation", "uncertainty_observation", "pattern_checkin", "light_observation"}:
        if stressed >= META_SUPPORT_OVERRIDE_THRESHOLD:
            fallback = {
                "kind": "gentle_clarify",
                "text": "i might be reading the moment carefully, but do you want comfort, space, or help sorting something out?",
                "topic_key": "meta_support_only",
                "base_score": 0.74,
                "score": 0.74,
                "memory_importance": 0.56,
                "fallback_kind": "meta_support_only",
                "action_confidence": 0.78,
                "interpretation_confidence": 0.70,
                "goal_alignment": 0.22,
            }
            _record_distribution_win(kind=fallback.get("kind", "gentle_clarify"), goal_name=active_goal_name, silence=False, fallback_kind="meta_support_only")
            return fallback, "Meta force_mode support_only redirected behavior toward supportive clarification.", state
    return chosen, reason, state




demo.launch(share=False, server_name="127.0.0.1", server_port=7860)


# =========================================================
# v33 meta mode refinement patch
# explicit modes, hysteresis, recovery, weighted outcomes
# =========================================================
META_MODES = {
    "balanced": {
        "drive_multipliers": {"reduce_stress": 1.0, "increase_engagement": 1.0, "explore_topic": 1.0, "clarify": 1.0, "maintain_connection": 1.0, "observe_silently": 1.0, "wait_for_user": 1.0},
        "silence_bias": 0.00,
        "variation_mult": 1.0,
    },
    "low_initiative": {
        "drive_multipliers": {"increase_engagement": 0.88, "explore_topic": 0.85, "maintain_connection": 0.92, "observe_silently": 1.18, "wait_for_user": 1.15},
        "silence_bias": 0.08,
        "variation_mult": 0.95,
    },
    "supportive": {
        "drive_multipliers": {"reduce_stress": 1.28, "clarify": 1.06, "maintain_connection": 1.08, "explore_topic": 0.86, "increase_engagement": 0.90},
        "silence_bias": 0.02,
        "variation_mult": 0.85,
    },
    "observational": {
        "drive_multipliers": {"observe_silently": 1.30, "wait_for_user": 1.18, "explore_topic": 0.90, "increase_engagement": 0.85, "maintain_connection": 0.94},
        "silence_bias": 0.10,
        "variation_mult": 0.90,
    },
    "exploratory": {
        "drive_multipliers": {"explore_topic": 1.24, "increase_engagement": 1.10, "clarify": 1.05, "observe_silently": 0.92, "wait_for_user": 0.94},
        "silence_bias": -0.02,
        "variation_mult": 1.12,
    },
}
MODE_SWITCH_THRESHOLD = 0.70
MODE_EXIT_THRESHOLD = 0.40
META_RECOVERY_SECONDS = 900.0
META_HISTORY_LIMIT = 10
SUCCESS_WEIGHT = 1.0
IGNORE_WEIGHT = -0.5
CONFUSION_WEIGHT = -0.7

_orig_default_meta_state_v33 = _default_meta_state
_orig_default_meta_feedback_v33 = _default_meta_feedback
_orig_compute_meta_control_v33 = _compute_meta_control
_orig_state_goal_drive_scores_v33 = _state_goal_drive_scores
_orig_small_variation_probability_v33 = _small_variation_probability
_orig_register_autonomous_message_v33 = register_autonomous_message


def _default_meta_state() -> dict:
    base = _orig_default_meta_state_v33()
    base.update({
        "interaction_mode": "balanced",
        "force_mode": "balanced",
        "mode_strength": 0.0,
        "recent_overactivity": 0.10,
        "silence_pressure": 0.12,
        "support_pressure": 0.10,
        "initiative_pressure": 0.55,
        "last_updated": now_iso(),
    })
    return base


def _default_meta_feedback() -> dict:
    base = _orig_default_meta_feedback_v33()
    base.setdefault("recent", [])
    base.setdefault("weighted", {})
    return base


def _mode_candidate_strengths(user_state: dict, initiative_state: dict, mood: dict, camera_state: dict) -> dict:
    scores = user_state.get("scores", {}) or {}
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    ignored = int(initiative_state.get("consecutive_ignored_initiations", 0) or 0)
    support = max(scores.get("stressed", 0.0), scores.get("fatigued", 0.0), _safe_float(camera_state.get("current", {}).get("tension_score", 0.0), 0.0))
    closed = scores.get("socially_closed", 0.0)
    open_ = scores.get("socially_open", 0.0)
    focused = scores.get("focused", 0.0)
    drifting = scores.get("drifting", 0.0)
    initiative = _safe_float((mood.get("behavior_modifiers", {}) or {}).get("initiative", 0.5), 0.5)
    return {
        "balanced": 0.45 + max(0.0, open_ - 0.3) * 0.2,
        "low_initiative": max(busy, min(1.0, ignored * 0.22), closed),
        "supportive": support,
        "observational": max(closed, busy * 0.9, max(0.0, 0.65 - initiative)),
        "exploratory": max(focused * 0.9, open_ * 0.7, max(0.0, 0.8 - drifting) * 0.4),
    }


def _select_meta_mode(prev_mode: str, strengths: dict) -> tuple[str, float]:
    prev_strength = _safe_float(strengths.get(prev_mode, 0.0), 0.0)
    best_mode, best_strength = max(strengths.items(), key=lambda kv: kv[1])
    if prev_mode and prev_mode in strengths:
        if prev_mode == best_mode:
            return prev_mode, best_strength
        if best_strength < MODE_SWITCH_THRESHOLD:
            return prev_mode, prev_strength
        if prev_strength > MODE_EXIT_THRESHOLD and best_strength - prev_strength < 0.12:
            return prev_mode, prev_strength
    if best_strength >= MODE_SWITCH_THRESHOLD:
        return best_mode, best_strength
    return prev_mode or "balanced", prev_strength if prev_mode in strengths else best_strength


def _weighted_outcome(meta_feedback: dict, behavior_type: str = "", goal_name: str = "") -> float:
    weighted = meta_feedback.get("weighted", {}) or {}
    vals = []
    if behavior_type and behavior_type in weighted:
        vals.append(_safe_float(weighted[behavior_type], 0.0))
    if goal_name and goal_name in weighted:
        vals.append(_safe_float(weighted[goal_name], 0.0))
    if not vals:
        return 0.0
    return _clamp(sum(vals) / max(1, len(vals)), -1.0, 1.0)


def _compute_meta_control(system: dict | None = None, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    system = system or load_goal_system()
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    prev = dict(system.get("meta_control", _default_meta_control()) or _default_meta_control())
    meta_state = dict(system.get("meta_state", _default_meta_state()) or _default_meta_state())
    meta_feedback = dict(system.get("meta_feedback", _default_meta_feedback()) or _default_meta_feedback())
    user_state = system.get("user_state", {}) or _default_user_state()
    base = _orig_compute_meta_control_v33(system=system, mood=mood, camera_state=camera_state, initiative_state=initiative_state)

    strengths = _mode_candidate_strengths(user_state, initiative_state, mood, camera_state)
    prev_mode = str(meta_state.get("interaction_mode", "balanced") or "balanced")
    mode, mode_strength = _select_meta_mode(prev_mode, strengths)

    last_ts = meta_state.get("last_updated", now_iso())
    try:
        dt = max(0.0, now_ts() - datetime.fromisoformat(str(last_ts)).timestamp())
    except Exception:
        dt = 0.0
    recovery = min(1.0, dt / META_RECOVERY_SECONDS) if META_RECOVERY_SECONDS > 0 else 1.0
    outcome_bias = _weighted_outcome(meta_feedback, meta_state.get("last_behavior_type", ""), meta_state.get("last_goal_name", ""))

    recent_over = _safe_float(meta_state.get("recent_overactivity", 0.1), 0.1)
    silence_pressure = _safe_float(meta_state.get("silence_pressure", 0.12), 0.12)
    initiative_pressure = _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55)
    support_pressure = _safe_float(meta_state.get("support_pressure", 0.10), 0.10)

    # smooth pressures and allow timed recovery from quiet modes
    silence_pressure = _clamp(recent_over * 0.18 + silence_pressure * (1.0 - 0.12) - recovery * 0.06 + max(0.0, -outcome_bias) * 0.04, 0.0, 1.0)
    initiative_pressure = _clamp(initiative_pressure * 0.88 + (0.56 + outcome_bias * 0.10 - silence_pressure * 0.12) * 0.12, 0.0, 1.0)
    support_pressure = _clamp(support_pressure * 0.86 + strengths.get("supportive", 0.0) * 0.14, 0.0, 1.0)

    mode_cfg = META_MODES.get(mode, META_MODES["balanced"])
    base["silence_bias"] = _clamp(base.get("silence_bias", 0.12) + mode_cfg.get("silence_bias", 0.0) + silence_pressure * 0.06, META_SILENCE_BIAS_MIN, META_SILENCE_BIAS_MAX)
    base["variation_chance"] = _clamp(base.get("variation_chance", 0.06) * _safe_float(mode_cfg.get("variation_mult", 1.0), 1.0), META_VARIATION_MIN, META_VARIATION_MAX)
    base["learning_rate"] = _clamp(base.get("learning_rate", 0.02), META_LEARNING_RATE_MIN, META_LEARNING_RATE_MAX)
    base["max_learning_influence"] = _clamp(base.get("max_learning_influence", 0.18), META_LEARNING_INFLUENCE_MIN, META_LEARNING_INFLUENCE_MAX)
    base["interaction_mode"] = mode
    base["mode_strength"] = round(mode_strength, 4)
    base["drive_mode_multipliers"] = _deepcopy_jsonable(mode_cfg.get("drive_multipliers", {}))
    base["reason"] = f"mode={mode} strength={mode_strength:.2f} outcome={outcome_bias:.2f} recover={recovery:.2f}"
    base["last_updated"] = now_iso()

    meta_state.update({
        "interaction_mode": mode,
        "force_mode": mode if mode != "balanced" and mode_strength >= MODE_SWITCH_THRESHOLD else "balanced",
        "mode_strength": round(mode_strength, 4),
        "recent_overactivity": round(_meta_blend(meta_state.get("recent_overactivity", 0.1), recent_over, alpha=0.8), 4),
        "silence_pressure": round(_meta_blend(meta_state.get("silence_pressure", 0.12), silence_pressure, alpha=0.8), 4),
        "support_pressure": round(_meta_blend(meta_state.get("support_pressure", 0.10), support_pressure, alpha=0.8), 4),
        "initiative_pressure": round(_meta_blend(meta_state.get("initiative_pressure", 0.55), initiative_pressure, alpha=0.8), 4),
        "last_updated": now_iso(),
    })
    system["meta_state"] = meta_state
    base["meta_state"] = _deepcopy_jsonable(meta_state)
    return base


def _state_goal_drive_scores(user_state: dict, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    base = _orig_state_goal_drive_scores_v33(user_state, mood=mood, camera_state=camera_state, initiative_state=initiative_state)
    system = load_goal_system()
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    mode = str(meta.get("interaction_mode", meta_state.get("interaction_mode", "balanced")) or "balanced")
    multipliers = (meta.get("drive_mode_multipliers", {}) or META_MODES.get(mode, META_MODES["balanced"]).get("drive_multipliers", {}))
    adjusted = dict(base)
    for k, mult in multipliers.items():
        if k in adjusted:
            adjusted[k] = max(0.0, _safe_float(adjusted.get(k, 0.0), 0.0) * _safe_float(mult, 1.0))
    # direct meta influence on drives
    adjusted["observe_silently"] = max(0.0, adjusted.get("observe_silently", 0.0) + _safe_float(meta_state.get("silence_pressure", 0.0), 0.0) * 0.25)
    adjusted["wait_for_user"] = max(0.0, adjusted.get("wait_for_user", 0.0) + _safe_float(meta_state.get("silence_pressure", 0.0), 0.0) * 0.18)
    adjusted["reduce_stress"] = max(0.0, adjusted.get("reduce_stress", 0.0) + _safe_float(meta_state.get("support_pressure", 0.0), 0.0) * 0.22)
    adjusted["increase_engagement"] = max(0.0, adjusted.get("increase_engagement", 0.0) + _safe_float(meta_state.get("initiative_pressure", 0.0), 0.0) * 0.14 - _safe_float(meta_state.get("silence_pressure", 0.0), 0.0) * 0.10)
    adjusted["explore_topic"] = max(0.0, adjusted.get("explore_topic", 0.0) + _safe_float(meta_state.get("initiative_pressure", 0.0), 0.0) * 0.10)
    return normalize_drives(adjusted, strength=_safe_float(meta.get("drive_normalization_strength", 0.82), 0.82))


def _small_variation_probability(decisiveness: float, goal_strength: float, confidence: float) -> float:
    prob = _orig_small_variation_probability_v33(decisiveness, goal_strength, confidence)
    try:
        meta = load_goal_system().get("meta_control", _default_meta_control()) or _default_meta_control()
        prob = prob * _safe_float(meta.get("variation_chance", prob), prob) / max(0.001, SMALL_VARIATION_CHANCE)
    except Exception:
        pass
    return max(0.0, min(0.16, round(prob, 3)))


def _record_meta_outcome(candidate_kind: str = "", goal_name: str = "", outcome_weight: float = 0.0):
    system = load_goal_system()
    system.setdefault("meta_feedback", _default_meta_feedback())
    feedback = system["meta_feedback"]
    feedback.setdefault("weighted", {})
    for key in filter(None, [candidate_kind, goal_name]):
        prev = _safe_float(feedback["weighted"].get(key, 0.0), 0.0)
        feedback["weighted"][key] = round(_clamp(prev * 0.85 + outcome_weight * 0.15, -1.0, 1.0), 4)
    recent = list(feedback.get("recent", []) or [])
    recent.append({"timestamp": now_iso(), "kind": candidate_kind, "goal": goal_name, "weight": round(outcome_weight, 3)})
    feedback["recent"] = recent[-META_HISTORY_LIMIT:]
    system["meta_feedback"] = feedback
    save_goal_system(system)


def register_autonomous_message(candidate: dict, message: str):
    _orig_register_autonomous_message_v33(candidate, message)
    try:
        system = load_goal_system()
        system.setdefault("meta_feedback", _default_meta_feedback())
        recent = list((system["meta_feedback"].get("recent") or []))
        recent.append({
            "timestamp": now_iso(),
            "kind": candidate.get("kind", "thought"),
            "goal": (system.get("active_goal", {}) or {}).get("name", ""),
            "response": None,
        })
        system["meta_feedback"]["recent"] = recent[-META_HISTORY_LIMIT:]
        meta_state = system.get("meta_state", _default_meta_state())
        meta_state["last_behavior_type"] = candidate.get("kind", "thought")
        meta_state["last_goal_name"] = (system.get("active_goal", {}) or {}).get("name", "")
        meta_state["last_updated"] = now_iso()
        system["meta_state"] = meta_state
        save_goal_system(system)
    except Exception:
        pass


def _meta_response_outcome_weight(response_text: str = "") -> float:
    txt = (response_text or "").lower().strip()
    if not txt:
        return IGNORE_WEIGHT
    confusion_markers = ["what do you mean", "confused", "huh", "what?", "why would you", "that makes no sense"]
    if any(m in txt for m in confusion_markers):
        return CONFUSION_WEIGHT
    return SUCCESS_WEIGHT


def maybe_mark_initiation_responded(user_text: str):
    state_before = expire_stale_pending_initiation(load_initiative_state())
    pending = state_before.get("pending_initiation") or {}
    had_pending = bool(pending and not pending.get("responded"))
    cand_kind = pending.get("candidate_kind", "") if had_pending else ""
    goal_name = ""
    try:
        goal_name = ((load_goal_system().get("active_goal", {}) or {}).get("name", ""))
    except Exception:
        goal_name = ""
    _orig = globals().get('_orig_maybe_mark_initiation_responded_v33')
    if _orig:
        result = _orig(user_text)
    else:
        if not had_pending:
            return False
        pending["responded"] = True
        state_before["pending_initiation"] = pending
        state_before["consecutive_ignored_initiations"] = 0
        save_initiative_state(state_before)
        result = True
    if result and had_pending:
        _record_meta_outcome(cand_kind, goal_name, _meta_response_outcome_weight(user_text))
        try:
            system = load_goal_system()
            recent = list((system.get("meta_feedback", {}) or {}).get("recent", []) or [])
            if recent:
                recent[-1]["response"] = True
                system.setdefault("meta_feedback", _default_meta_feedback())
                system["meta_feedback"]["recent"] = recent[-META_HISTORY_LIMIT:]
                save_goal_system(system)
        except Exception:
            pass
    return result




# =========================================================
# V34 META MODE PROFILE + PERSISTENCE + CUSTOM MODES PATCH
# =========================================================
META_MODE_CONFIDENCE_ALPHA = 0.82
META_MODE_STRENGTH_DECAY_PER_SECOND = 0.0009
META_MODE_RECOVERY_PER_SECOND = 0.0008
META_LONG_PATTERN_WINDOW_SECONDS = 300.0
META_SHORT_RECENT_LIMIT = 10
META_MIN_MODE_CONFIDENCE = 0.05
META_MAX_MODE_CONFIDENCE = 0.98

META_MODE_BLOCK_RE = re.compile(r"```META_MODE\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)

META_MODES = {
    "balanced": {
        "initiative_bias": 0.00,
        "silence_bias": 0.00,
        "exploration_drive": 1.00,
        "support_drive": 1.00,
        "connection_drive": 1.00,
        "novelty_preference": 1.00,
        "repetition_tolerance": 1.00,
        "variation_mult": 1.00,
        "drive_multipliers": {
            "reduce_stress": 1.00, "increase_engagement": 1.00, "explore_topic": 1.00,
            "clarify": 1.00, "maintain_connection": 1.00, "observe_silently": 1.00,
            "wait_for_user": 1.00,
        },
    },
    "low_initiative": {
        "initiative_bias": -0.18,
        "silence_bias": 0.10,
        "exploration_drive": 0.90,
        "support_drive": 0.96,
        "connection_drive": 0.94,
        "novelty_preference": 0.88,
        "repetition_tolerance": 0.92,
        "variation_mult": 0.92,
        "drive_multipliers": {
            "increase_engagement": 0.88, "explore_topic": 0.84, "maintain_connection": 0.92,
            "observe_silently": 1.20, "wait_for_user": 1.16,
        },
    },
    "supportive": {
        "initiative_bias": -0.02,
        "silence_bias": 0.03,
        "exploration_drive": 0.88,
        "support_drive": 1.24,
        "connection_drive": 1.10,
        "novelty_preference": 0.90,
        "repetition_tolerance": 1.02,
        "variation_mult": 0.84,
        "drive_multipliers": {
            "reduce_stress": 1.30, "clarify": 1.08, "maintain_connection": 1.10,
            "explore_topic": 0.86, "increase_engagement": 0.90,
        },
    },
    "observational": {
        "initiative_bias": -0.20,
        "silence_bias": 0.12,
        "exploration_drive": 0.92,
        "support_drive": 0.98,
        "connection_drive": 0.94,
        "novelty_preference": 0.86,
        "repetition_tolerance": 0.88,
        "variation_mult": 0.90,
        "drive_multipliers": {
            "observe_silently": 1.32, "wait_for_user": 1.20, "explore_topic": 0.90,
            "increase_engagement": 0.84, "maintain_connection": 0.94,
        },
    },
    "exploratory": {
        "initiative_bias": 0.08,
        "silence_bias": -0.02,
        "exploration_drive": 1.24,
        "support_drive": 0.92,
        "connection_drive": 1.04,
        "novelty_preference": 1.12,
        "repetition_tolerance": 0.86,
        "variation_mult": 1.10,
        "drive_multipliers": {
            "explore_topic": 1.26, "increase_engagement": 1.12, "clarify": 1.04,
            "observe_silently": 0.92, "wait_for_user": 0.94,
        },
    },
}

_orig_process_ava_action_blocks_v34 = process_ava_action_blocks
_orig_default_goal_system_v34 = default_goal_system
_orig_load_goal_system_v34 = load_goal_system
_orig_save_goal_system_v34 = save_goal_system
_orig_default_meta_state_v34 = _default_meta_state
_orig_default_meta_feedback_v34 = _default_meta_feedback
_orig_ensure_meta_tables_v34 = _ensure_meta_tables
_orig_decay_meta_state_v34 = _decay_meta_state
_orig_apply_meta_feedback_v34 = _apply_meta_feedback
_orig_mode_candidate_strengths_v34 = _mode_candidate_strengths
_orig_select_meta_mode_v34 = _select_meta_mode
_orig_compute_meta_control_v34 = _compute_meta_control
_orig_state_goal_drive_scores_v34 = _state_goal_drive_scores


def _default_meta_state() -> dict:
    base = _orig_default_meta_state_v34()
    base.setdefault("mode_confidence", 0.55)
    base.setdefault("mode_strength", 0.0)
    base.setdefault("time_in_mode", 0.0)
    base.setdefault("mode_started_at", now_iso())
    base.setdefault("last_mode_switch_at", now_iso())
    base.setdefault("meta_recovery", 0.0)
    return base


def _default_meta_feedback() -> dict:
    base = _orig_default_meta_feedback_v34()
    base.setdefault("recent", [])
    base.setdefault("long_window", {})
    base.setdefault("success_rate", {})
    base.setdefault("by_person_behavior", {})
    return base


def default_goal_system() -> dict:
    base = _orig_default_goal_system_v34()
    base.setdefault("custom_meta_modes", {})
    base.setdefault("meta_state", _default_meta_state())
    base.setdefault("meta_feedback", _default_meta_feedback())
    return base


def load_goal_system() -> dict:
    system = _orig_load_goal_system_v34()
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    system.setdefault("custom_meta_modes", {})
    return system


def save_goal_system(system: dict):
    defaults = default_goal_system()
    for key, value in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(value) if isinstance(value, (dict, list)) else value
    _orig_save_goal_system_v34(system)


def _ensure_meta_tables(system: dict | None = None) -> dict:
    system = _orig_ensure_meta_tables_v34(system)
    system.setdefault("custom_meta_modes", {})
    return system


def _sanitize_mode_profile(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    profile = {
        "initiative_bias": _clamp(_safe_float(raw.get("initiative_bias", 0.0), 0.0), -0.35, 0.35),
        "silence_bias": _clamp(_safe_float(raw.get("silence_bias", 0.0), 0.0), -0.10, 0.30),
        "exploration_drive": _clamp(_safe_float(raw.get("exploration_drive", 1.0), 1.0), 0.70, 1.35),
        "support_drive": _clamp(_safe_float(raw.get("support_drive", 1.0), 1.0), 0.70, 1.40),
        "connection_drive": _clamp(_safe_float(raw.get("connection_drive", 1.0), 1.0), 0.70, 1.35),
        "novelty_preference": _clamp(_safe_float(raw.get("novelty_preference", 1.0), 1.0), 0.70, 1.35),
        "repetition_tolerance": _clamp(_safe_float(raw.get("repetition_tolerance", 1.0), 1.0), 0.70, 1.30),
        "variation_mult": _clamp(_safe_float(raw.get("variation_mult", 1.0), 1.0), 0.70, 1.30),
        "drive_multipliers": {},
    }
    for k, v in dict(raw.get("drive_multipliers", {}) or {}).items():
        try:
            profile["drive_multipliers"][str(k)] = _clamp(float(v), 0.60, 1.60)
        except Exception:
            continue
    return profile


def _all_meta_modes(system: dict | None = None) -> dict:
    system = system or load_goal_system()
    modes = {k: _deepcopy_jsonable(v) for k, v in META_MODES.items()}
    for name, profile in dict(system.get("custom_meta_modes", {}) or {}).items():
        safe = _sanitize_mode_profile(profile)
        if safe:
            modes[str(name).strip().lower()] = safe
    return modes


def upsert_custom_meta_mode(name: str, profile: dict) -> str:
    mode_name = str(name or "").strip().lower().replace(" ", "_")
    if not mode_name:
        return "❌ Meta mode name missing."
    safe = _sanitize_mode_profile(profile)
    if not safe:
        return "❌ Invalid meta mode profile."
    system = load_goal_system()
    custom = dict(system.get("custom_meta_modes", {}) or {})
    custom[mode_name] = safe
    system["custom_meta_modes"] = custom
    save_goal_system(system)
    return f"✅ Ava saved custom meta mode '{mode_name}'"


def process_ava_action_blocks(reply_text: str, person_id: str, latest_user_input: str = "") -> tuple[str, list[str]]:
    cleaned, actions = _orig_process_ava_action_blocks_v34(reply_text, person_id, latest_user_input=latest_user_input)
    def meta_mode_repl(match):
        block = parse_key_values(match.group(1))
        action = str(block.get("action", "add")).strip().lower()
        if action not in {"add", "update"}:
            actions.append("❌ Unsupported META_MODE action.")
            return ""
        name = block.get("name", "").strip()
        profile = {
            "initiative_bias": block.get("initiative_bias", 0.0),
            "silence_bias": block.get("silence_bias", 0.0),
            "exploration_drive": block.get("exploration_drive", 1.0),
            "support_drive": block.get("support_drive", 1.0),
            "connection_drive": block.get("connection_drive", 1.0),
            "novelty_preference": block.get("novelty_preference", 1.0),
            "repetition_tolerance": block.get("repetition_tolerance", 1.0),
            "variation_mult": block.get("variation_mult", 1.0),
            "drive_multipliers": parse_key_values(block.get("drive_multipliers", "")) if block.get("drive_multipliers") else {},
        }
        actions.append(upsert_custom_meta_mode(name, profile))
        return ""
    cleaned = META_MODE_BLOCK_RE.sub(meta_mode_repl, cleaned)
    return cleaned.strip(), actions


def _decay_meta_state(meta_state: dict, dt_seconds: float) -> dict:
    ms = dict(_orig_decay_meta_state_v34(meta_state, dt_seconds))
    dt = max(0.0, _safe_float(dt_seconds, 0.0))
    mode_strength = _safe_float(ms.get("mode_strength", 0.0), 0.0)
    mode_conf = _safe_float(ms.get("mode_confidence", 0.55), 0.55)
    mode_decay = min(0.35, dt * META_MODE_STRENGTH_DECAY_PER_SECOND)
    recovery = min(0.20, dt * META_MODE_RECOVERY_PER_SECOND)
    ms["mode_strength"] = round(max(0.0, mode_strength * (1.0 - mode_decay)), 4)
    ms["mode_confidence"] = round(_clamp(mode_conf * (1.0 - mode_decay * 0.35) + 0.55 * recovery, META_MIN_MODE_CONFIDENCE, META_MAX_MODE_CONFIDENCE), 4)
    ms["meta_recovery"] = round(_clamp(_safe_float(ms.get("meta_recovery", 0.0), 0.0) * (1.0 - mode_decay) + recovery, 0.0, 1.0), 4)
    # drift back to balanced if quiet for a long time
    last_switch = ms.get("last_mode_switch_at") or ms.get("last_updated")
    quiet_seconds = _goal_seconds_since(last_switch)
    if quiet_seconds > META_RECOVERY_SECONDS:
        ms["silence_pressure"] = round(max(0.0, _safe_float(ms.get("silence_pressure", 0.12), 0.12) - 0.06 * min(1.0, (quiet_seconds - META_RECOVERY_SECONDS) / META_RECOVERY_SECONDS)), 4)
        ms["initiative_pressure"] = round(_clamp(_safe_float(ms.get("initiative_pressure", 0.55), 0.55) + 0.04 * min(1.0, (quiet_seconds - META_RECOVERY_SECONDS) / META_RECOVERY_SECONDS), 0.0, META_INITIATIVE_PRESSURE_MAX), 4)
    return ms


def _weighted_outcome_value(event: dict) -> float:
    if not isinstance(event, dict):
        return 0.0
    status = str(event.get("status", ""))
    if status == "success":
        return SUCCESS_WEIGHT
    if status == "ignored":
        return IGNORE_WEIGHT
    if status == "confusion":
        return CONFUSION_WEIGHT
    return SUCCESS_WEIGHT if bool(event.get("success")) else IGNORE_WEIGHT


def _long_window_meta_stats(feedback: dict | None = None) -> dict:
    feedback = feedback or _default_meta_feedback()
    recent = list(feedback.get("recent", []) or [])
    now = now_ts()
    window = []
    for row in recent:
        try:
            ts = datetime.fromisoformat(str(row.get("timestamp", "")).replace('Z', '+00:00'))
            tsv = ts.timestamp() if ts.tzinfo else ts.replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            continue
        if (now - tsv) <= META_LONG_PATTERN_WINDOW_SECONDS:
            window.append(row)
    total = len(window)
    success = sum(1 for r in window if _weighted_outcome_value(r) > 0)
    ignored = sum(1 for r in window if str(r.get("status", "")) == "ignored" or (not r.get("success") and str(r.get("status", "")) != "confusion"))
    confusion = sum(1 for r in window if str(r.get("status", "")) == "confusion")
    success_rate = (success / total) if total else 0.5
    return {
        "window_total": total,
        "success_rate": round(success_rate, 4),
        "ignored_rate": round((ignored / total) if total else 0.0, 4),
        "confusion_rate": round((confusion / total) if total else 0.0, 4),
    }


def _apply_meta_feedback(success: bool, behavior_type: str = "", goal_name: str = "", person_id: str = "", status: str | None = None):
    system = _ensure_meta_tables(load_goal_system())
    feedback = system.get("meta_feedback", _default_meta_feedback()) or _default_meta_feedback()
    _bump_meta_feedback(feedback.setdefault("by_behavior", {}), behavior_type, success)
    _bump_meta_feedback(feedback.setdefault("by_goal", {}), goal_name, success)
    if person_id and behavior_type:
        _bump_meta_feedback(feedback.setdefault("by_person_behavior", {}), f"{person_id}:{behavior_type}", success)
    recent = list(feedback.get("recent", []) or [])[-(META_SHORT_RECENT_LIMIT * 3):]
    entry = {
        "timestamp": now_iso(),
        "success": bool(success),
        "behavior": behavior_type,
        "goal": goal_name,
        "person_id": person_id or get_active_person_id(),
        "status": status or ("success" if success else "ignored"),
    }
    recent.append(entry)
    feedback["recent"] = recent[-(META_SHORT_RECENT_LIMIT * 3):]
    feedback["long_window"] = _long_window_meta_stats(feedback)
    # weighted success memory
    for key in [behavior_type, goal_name, f"{person_id}:{behavior_type}" if person_id and behavior_type else ""]:
        if not key:
            continue
        weighted = float((feedback.setdefault("weighted", {}) or {}).get(key, 0.0) or 0.0)
        weighted = weighted * (1.0 - META_FEEDBACK_ALPHA) + _weighted_outcome_value(entry) * META_FEEDBACK_ALPHA
        feedback.setdefault("weighted", {})[key] = round(_clamp(weighted, -1.0, 1.0), 4)
    feedback.setdefault("success_rate", {})[behavior_type or "unknown"] = feedback.get("long_window", {}).get("success_rate", 0.5)
    system["meta_feedback"] = feedback

    meta_state = _decay_meta_state(system.get("meta_state", _default_meta_state()) or _default_meta_state(), 0.0)
    outcome = _weighted_outcome_value(entry)
    if outcome > 0:
        meta_state["confidence_in_user_engagement"] = round(_meta_blend(meta_state.get("confidence_in_user_engagement", 0.6), min(1.0, _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6) + 0.16), META_STATE_ALPHA), 4)
        meta_state["silence_pressure"] = round(_meta_blend(meta_state.get("silence_pressure", 0.12), max(0.0, _safe_float(meta_state.get("silence_pressure", 0.12), 0.12) - 0.10), META_STATE_ALPHA), 4)
        meta_state["initiative_pressure"] = round(_meta_blend(meta_state.get("initiative_pressure", 0.55), min(1.0, _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55) + 0.07), META_STATE_ALPHA), 4)
    else:
        meta_state["confidence_in_user_engagement"] = round(_meta_blend(meta_state.get("confidence_in_user_engagement", 0.6), max(0.0, _safe_float(meta_state.get("confidence_in_user_engagement", 0.6), 0.6) - 0.14), META_STATE_ALPHA), 4)
        meta_state["silence_pressure"] = round(_meta_blend(meta_state.get("silence_pressure", 0.12), min(1.0, _safe_float(meta_state.get("silence_pressure", 0.12), 0.12) + 0.14), META_STATE_ALPHA), 4)
        meta_state["recent_overactivity"] = round(_meta_blend(meta_state.get("recent_overactivity", 0.10), min(1.0, _safe_float(meta_state.get("recent_overactivity", 0.10), 0.10) + 0.12), META_STATE_ALPHA), 4)
        meta_state["initiative_pressure"] = round(_meta_blend(meta_state.get("initiative_pressure", 0.55), max(0.0, _safe_float(meta_state.get("initiative_pressure", 0.55), 0.55) - 0.07), META_STATE_ALPHA), 4)
    meta_state["last_updated"] = now_iso()
    system["meta_state"] = meta_state
    save_goal_system(system)


def _mode_candidate_strengths(user_state: dict, initiative_state: dict, mood: dict, camera_state: dict, system: dict | None = None) -> dict:
    system = system or load_goal_system()
    strengths = dict(_orig_mode_candidate_strengths_v34(user_state, initiative_state, mood, camera_state))
    feedback = system.get("meta_feedback", _default_meta_feedback()) or _default_meta_feedback()
    long_stats = feedback.get("long_window", {}) or {}
    success_rate = _safe_float(long_stats.get("success_rate", 0.5), 0.5)
    ignored_rate = _safe_float(long_stats.get("ignored_rate", 0.0), 0.0)
    scores = user_state.get("scores", {}) or {}
    stressed = _safe_float(scores.get("stressed", 0.0), 0.0)
    focused = _safe_float(scores.get("focused", 0.0), 0.0)
    drifting = _safe_float(scores.get("drifting", 0.0), 0.0)
    socially_open = _safe_float(scores.get("socially_open", 0.0), 0.0)
    socially_closed = _safe_float(scores.get("socially_closed", 0.0), 0.0)
    if success_rate < 0.35 and ignored_rate > 0.40:
        strengths["low_initiative"] = strengths.get("low_initiative", 0.0) + 0.12
        strengths["observational"] = strengths.get("observational", 0.0) + 0.08
    if stressed > 0.68:
        strengths["supportive"] = strengths.get("supportive", 0.0) + 0.12
    if focused > 0.70 and socially_open > 0.45:
        strengths["exploratory"] = strengths.get("exploratory", 0.0) + 0.08
    if drifting > 0.62 or socially_closed > 0.70:
        strengths["observational"] = strengths.get("observational", 0.0) + 0.10
    return strengths


def _select_meta_mode(prev_mode: str, strengths: dict, meta_state: dict | None = None) -> tuple[str, float, float]:
    meta_state = meta_state or _default_meta_state()
    prev_strength = _safe_float(strengths.get(prev_mode, 0.0), 0.0)
    best_mode, best_strength = max((strengths or {"balanced": 0.45}).items(), key=lambda kv: kv[1])
    prev_conf = _safe_float(meta_state.get("mode_confidence", 0.55), 0.55)
    if prev_mode and prev_mode in strengths:
        if prev_mode == best_mode:
            new_conf = _clamp(prev_conf * META_MODE_CONFIDENCE_ALPHA + best_strength * (1.0 - META_MODE_CONFIDENCE_ALPHA), META_MIN_MODE_CONFIDENCE, META_MAX_MODE_CONFIDENCE)
            return prev_mode, best_strength, new_conf
        if best_strength < MODE_SWITCH_THRESHOLD:
            return prev_mode, prev_strength, max(META_MIN_MODE_CONFIDENCE, prev_conf * 0.985)
        if prev_strength > MODE_EXIT_THRESHOLD and best_strength - prev_strength < 0.12:
            return prev_mode, prev_strength, max(META_MIN_MODE_CONFIDENCE, prev_conf * 0.99)
    if best_strength >= MODE_SWITCH_THRESHOLD:
        new_conf = _clamp(0.45 + best_strength * 0.40, META_MIN_MODE_CONFIDENCE, META_MAX_MODE_CONFIDENCE)
        return best_mode, best_strength, new_conf
    return prev_mode or "balanced", prev_strength if prev_mode in strengths else best_strength, max(META_MIN_MODE_CONFIDENCE, prev_conf * 0.99)


def _compute_meta_control(system: dict | None = None, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    system = system or load_goal_system()
    mood = mood or load_mood()
    camera_state = camera_state or load_camera_state()
    initiative_state = initiative_state or load_initiative_state()
    mc = dict(_orig_compute_meta_control_v34(system=system, mood=mood, camera_state=camera_state, initiative_state=initiative_state))
    system = _ensure_meta_tables(system)
    meta_state = _decay_meta_state(system.get("meta_state", _default_meta_state()) or _default_meta_state(), _goal_seconds_since((system.get("meta_state", {}) or {}).get("last_updated")))
    feedback = system.get("meta_feedback", _default_meta_feedback()) or _default_meta_feedback()
    long_stats = _long_window_meta_stats(feedback)
    feedback["long_window"] = long_stats
    user_state = system.get("user_state", {}) or _default_user_state()
    strengths = _mode_candidate_strengths(user_state, initiative_state, mood, camera_state, system=system)
    chosen_mode, strength, mode_conf = _select_meta_mode(str(meta_state.get("interaction_mode", "balanced")), strengths, meta_state=meta_state)
    prev_mode = str(meta_state.get("interaction_mode", "balanced"))
    if chosen_mode != prev_mode:
        meta_state["mode_started_at"] = now_iso()
        meta_state["last_mode_switch_at"] = now_iso()
        meta_state["time_in_mode"] = 0.0
    else:
        meta_state["time_in_mode"] = round(_goal_seconds_since(meta_state.get("mode_started_at")), 3)
    meta_state["interaction_mode"] = chosen_mode
    meta_state["mode_confidence"] = round(mode_conf, 4)
    meta_state["mode_strength"] = round(_clamp(strength, 0.0, 1.0), 4)
    # force modes with authority
    force_mode = str(meta_state.get("force_mode", "balanced"))
    busy = _safe_float(initiative_state.get("last_busy_score", 0.0), 0.0)
    ignored = int(initiative_state.get("consecutive_ignored_initiations", 0) or 0)
    stressed = _safe_float(user_state.get("scores", {}).get("stressed", 0.0), 0.0)
    if stressed >= META_FORCE_STRESS_THRESHOLD:
        force_mode = "supportive"
    elif busy >= META_FORCE_BUSY_THRESHOLD or ignored >= META_FORCE_IGNORE_THRESHOLD:
        force_mode = "low_initiative"
    elif _safe_float(meta_state.get("silence_pressure", 0.12), 0.12) >= META_SILENCE_OVERRIDE_THRESHOLD:
        force_mode = "observational"
    elif _safe_float(meta_state.get("meta_recovery", 0.0), 0.0) > 0.45 and long_stats.get("success_rate", 0.5) >= 0.45:
        force_mode = "balanced"
    meta_state["force_mode"] = force_mode
    # explicit mode profile applied to control knobs
    modes = _all_meta_modes(system)
    profile = modes.get(force_mode if force_mode and force_mode != "balanced" else chosen_mode, modes.get("balanced", {}))
    mc["interaction_mode"] = chosen_mode
    mc["force_mode"] = force_mode
    mc["mode_confidence"] = meta_state.get("mode_confidence", 0.55)
    mc["time_in_mode"] = meta_state.get("time_in_mode", 0.0)
    mc["silence_bias"] = _clamp(_safe_float(mc.get("silence_bias", 0.12), 0.12) + _safe_float(profile.get("silence_bias", 0.0), 0.0), META_SILENCE_BIAS_MIN, META_SILENCE_BIAS_MAX)
    mc["variation_chance"] = _clamp(_safe_float(mc.get("variation_chance", 0.06), 0.06) * _safe_float(profile.get("variation_mult", 1.0), 1.0), META_VARIATION_MIN, META_VARIATION_MAX)
    mc["initiative_bias"] = _clamp(_safe_float(profile.get("initiative_bias", 0.0), 0.0), -0.35, 0.35)
    reason_bits = [f"mode={chosen_mode}", f"force={force_mode}", f"mode_conf={round(meta_state.get('mode_confidence', 0.55), 3)}", f"success_rate={long_stats.get('success_rate', 0.5)}"]
    mc["reason"] = "; ".join(reason_bits)
    mc["last_updated"] = now_iso()
    system["meta_state"] = meta_state
    system["meta_feedback"] = feedback
    save_goal_system(system)
    return mc


def _state_goal_drive_scores(user_state: dict, mood: dict | None = None, camera_state: dict | None = None, initiative_state: dict | None = None) -> dict:
    base = dict(_orig_state_goal_drive_scores_v34(user_state, mood=mood, camera_state=camera_state, initiative_state=initiative_state))
    system = load_goal_system()
    meta = system.get("meta_control", _default_meta_control()) or _default_meta_control()
    meta_state = system.get("meta_state", _default_meta_state()) or _default_meta_state()
    modes = _all_meta_modes(system)
    mode_name = str(meta_state.get("force_mode") or meta_state.get("interaction_mode") or "balanced")
    profile = modes.get(mode_name, modes.get("balanced", {}))
    # explicit drive-level influence
    for drive, mult in dict(profile.get("drive_multipliers", {}) or {}).items():
        if drive in base:
            base[drive] = base.get(drive, 0.0) * _safe_float(mult, 1.0)
    initiative_bias = _safe_float(meta.get("initiative_bias", 0.0), 0.0)
    if initiative_bias < 0:
        base["observe_silently"] = base.get("observe_silently", 0.0) + abs(initiative_bias) * 0.18
        base["wait_for_user"] = base.get("wait_for_user", 0.0) + abs(initiative_bias) * 0.12
    else:
        base["increase_engagement"] = base.get("increase_engagement", 0.0) + initiative_bias * 0.10
        base["explore_topic"] = base.get("explore_topic", 0.0) + initiative_bias * 0.08
    base["reduce_stress"] = base.get("reduce_stress", 0.0) * _safe_float(profile.get("support_drive", 1.0), 1.0)
    base["maintain_connection"] = base.get("maintain_connection", 0.0) * _safe_float(profile.get("connection_drive", 1.0), 1.0)
    base["explore_topic"] = base.get("explore_topic", 0.0) * _safe_float(profile.get("exploration_drive", 1.0), 1.0)
    # gentle drift back to balanced through normalized drives
    return normalize_drives(base, strength=_safe_float(meta.get("drive_normalization_strength", 0.82), 0.82))


# === v35 stability fix: iso_to_ts + guarded goal/self-model loading ===
from datetime import datetime

_GOAL_SYSTEM_LOADING = False
_SELF_MODEL_LOADING = False


def iso_to_ts(value) -> float:
    if value is None:
        return 0.0
    try:
        s = str(value).strip()
        if not s:
            return 0.0
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return float(datetime.fromisoformat(s).timestamp())
    except Exception:
        return 0.0


def _raw_load_self_model_v35() -> dict:
    if SELF_MODEL_PATH.exists():
        try:
            with open(SELF_MODEL_PATH, 'r', encoding='utf-8') as f:
                model = json.load(f)
        except Exception as e:
            print(f"Self model load error: {e}")
            model = default_self_model()
    else:
        model = default_self_model()
    defaults = default_self_model()
    for key, default in defaults.items():
        if key not in model:
            model[key] = _deepcopy_jsonable(default) if isinstance(default, (dict, list)) else default
    return model


def load_self_model() -> dict:
    global _SELF_MODEL_LOADING
    model = _raw_load_self_model_v35()
    if _SELF_MODEL_LOADING or _GOAL_SYSTEM_LOADING:
        return model
    try:
        _SELF_MODEL_LOADING = True
        try:
            system = load_goal_system()
            goals, questions = derive_goal_lists_from_system(system)
            model['current_goals'] = goals
            model['curiosity_questions'] = questions
            model['goal_system_summary'] = [
                {
                    'text': g.get('text', ''),
                    'priority': round(float(g.get('current_priority', 0.0)), 2),
                    'horizon': g.get('horizon', 'short_term'),
                    'kind': g.get('kind', 'goal'),
                }
                for g in system.get('goals', [])[:10]
            ]
            model['active_goal'] = system.get('active_goal', {})
            model['goal_blend'] = system.get('goal_blend', [])[:3]
        except Exception as e:
            print(f"Goal system sync error: {e}")
    finally:
        _SELF_MODEL_LOADING = False
    return model


def _raw_load_goal_system_v35() -> dict:
    if GOAL_SYSTEM_PATH.exists():
        try:
            with open(GOAL_SYSTEM_PATH, 'r', encoding='utf-8') as f:
                system = json.load(f)
        except Exception as e:
            print(f"Goal system load error: {e}")
            system = default_goal_system()
    else:
        system = default_goal_system()
    defaults = default_goal_system()
    for key, default in defaults.items():
        if key not in system:
            system[key] = _deepcopy_jsonable(default) if isinstance(default, (dict, list)) else default
    system.setdefault('custom_meta_modes', {})
    return system


def load_goal_system() -> dict:
    global _GOAL_SYSTEM_LOADING
    if _GOAL_SYSTEM_LOADING:
        return _raw_load_goal_system_v35()
    try:
        _GOAL_SYSTEM_LOADING = True
        system = _raw_load_goal_system_v35()
        if not system.get('goals') and not _SELF_MODEL_LOADING:
            try:
                model = _raw_load_self_model_v35()
                for text in model.get('current_goals', []) or []:
                    system['goals'].append(make_goal_entry(text, kind='goal', horizon='medium_term', importance=0.72, urgency=0.48, source='migration'))
                for text in model.get('curiosity_questions', []) or []:
                    system['goals'].append(make_goal_entry(text, kind='question', horizon='short_term', importance=0.56, urgency=0.58, source='migration'))
            except Exception:
                pass
        system = recalculate_goal_priorities(system)
        system = recalculate_operational_goals(system, context_text='', mood=load_mood())
        try:
            save_goal_system(system)
        except Exception as e:
            print(f"Goal system save error: {e}")
        return system
    finally:
        _GOAL_SYSTEM_LOADING = False


# =========================================================
# CANONICAL CHAT HISTORY HELPERS
# =========================================================
_CANONICAL_CHAT_HISTORY: list[dict] = []

def _extract_text_content(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "text" in value:
            return _extract_text_content(value.get("text"))
        if "content" in value:
            return _extract_text_content(value.get("content"))
        return ""
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            part = _extract_text_content(item)
            if part:
                parts.append(part)
        return "\n".join(parts).strip()
    return str(value)

def _normalize_history_entry(entry):
    if isinstance(entry, dict):
        role = str(entry.get("role", "assistant") or "assistant")
        content = _extract_text_content(entry.get("content", ""))
        return {"role": role, "content": content}
    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
        return {"role": str(entry[0] or "assistant"), "content": _extract_text_content(entry[1])}
    return None

def _normalize_history(history):
    out = []
    for item in list(history or []):
        norm = _normalize_history_entry(item)
        if norm is not None:
            out.append(norm)
    return out

def _history_key(entry):
    e = _normalize_history_entry(entry)
    if not e:
        return None
    return (e["role"], e["content"])

def _merge_histories(base_history, new_history):
    merged = []
    seen = set()
    for seq in (_normalize_history(base_history), _normalize_history(new_history)):
        for item in seq:
            key = _history_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged

def _set_canonical_history(history):
    global _CANONICAL_CHAT_HISTORY
    _CANONICAL_CHAT_HISTORY = _normalize_history(history)
    return list(_CANONICAL_CHAT_HISTORY)

def _get_canonical_history():
    return list(_normalize_history(_CANONICAL_CHAT_HISTORY))

def _sync_canonical_history(history):
    global _CANONICAL_CHAT_HISTORY
    incoming = _normalize_history(history)
    if not _CANONICAL_CHAT_HISTORY:
        _CANONICAL_CHAT_HISTORY = list(incoming)
        return list(_CANONICAL_CHAT_HISTORY)
    if not incoming:
        return list(_normalize_history(_CANONICAL_CHAT_HISTORY))
    _CANONICAL_CHAT_HISTORY = _merge_histories(_CANONICAL_CHAT_HISTORY, incoming)
    return list(_normalize_history(_CANONICAL_CHAT_HISTORY))


# Initialize canonical chat history at startup.
_set_canonical_history([])



# === BRAIN STAGE 3 OVERLAY START ===
try:
    from brain.selfstate import is_selfstate_query, build_selfstate_reply, startup_health_banner
    from brain.output_guard import scrub_visible_reply
    from brain.camera_live import read_fresh_frame
    from brain.health_runtime import lightweight_health_check, get_health, health_behavior_modifiers
except Exception as _brain_stage3_import_error:
    print("[brain-stage3] import error:", _brain_stage3_import_error)

def _brain_stage3_print_startup_health():
    try:
        print(startup_health_banner(lightweight_health_check()))
    except Exception as e:
        print("[startup-selftest] FAILED:", e)

_brain_stage3_print_startup_health()

try:
    _orig_chat_fn_stage3 = chat_fn
except Exception:
    _orig_chat_fn_stage3 = None

if _orig_chat_fn_stage3 is not None:
    def chat_fn(*args, **kwargs):
        try:
            user_text = ""
            if len(args) >= 2:
                maybe_message = args[1]
                if isinstance(maybe_message, str):
                    user_text = maybe_message
                elif isinstance(maybe_message, dict):
                    user_text = str(maybe_message.get("text", ""))
                elif isinstance(maybe_message, list) and maybe_message:
                    first = maybe_message[0]
                    if isinstance(first, dict):
                        user_text = str(first.get("text", ""))
            if is_selfstate_query(user_text):
                mood = {}
                try:
                    mood = globals().get("get_current_mood", lambda: {})() or {}
                except Exception:
                    mood = {}
                health = lightweight_health_check()
                reply = build_selfstate_reply(health, mood, tendency="balanced")
                if len(args) >= 1 and isinstance(args[0], list):
                    history = list(args[0])
                    history.append({"role": "user", "content": user_text})
                    history.append({"role": "assistant", "content": scrub_visible_reply(reply)})
                    # preserve broad gradio shapes: return history first, then clear text box if present
                    if len(args) >= 2:
                        return history, ""
                    return history
        except Exception as e:
            print("[brain-stage3] selfstate route failed:", e)
        out = _orig_chat_fn_stage3(*args, **kwargs)
        try:
            if isinstance(out, tuple) and out:
                lst = list(out)
                for i, v in enumerate(lst):
                    if isinstance(v, str):
                        lst[i] = scrub_visible_reply(v)
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict) and item.get("role") == "assistant" and isinstance(item.get("content"), str):
                                item["content"] = scrub_visible_reply(item["content"])
                return tuple(lst)
            if isinstance(out, str):
                return scrub_visible_reply(out)
        except Exception as e:
            print("[brain-stage3] scrub failed:", e)
        return out

try:
    _orig_generate_autonomous_message_stage3 = generate_autonomous_message
except Exception:
    _orig_generate_autonomous_message_stage3 = None

if _orig_generate_autonomous_message_stage3 is not None:
    def generate_autonomous_message(*args, **kwargs):
        out = _orig_generate_autonomous_message_stage3(*args, **kwargs)
        try:
            if isinstance(out, str):
                return scrub_visible_reply(out)
        except Exception:
            pass
        return out

try:
    _orig_camera_tick_fn_stage3 = camera_tick_fn
except Exception:
    _orig_camera_tick_fn_stage3 = None

if _orig_camera_tick_fn_stage3 is not None:
    def camera_tick_fn(*args, **kwargs):
        try:
            frame, status = read_fresh_frame()
            globals()["_BRAIN_STAGE3_CAMERA_STATUS"] = status
            if frame is not None:
                globals()["_BRAIN_STAGE3_LAST_FRAME"] = frame
        except Exception as e:
            print("[brain-stage3] camera refresh failed:", e)
        out = _orig_camera_tick_fn_stage3(*args, **kwargs)
        try:
            if isinstance(out, tuple):
                lst = list(out)
                # scrub assistant text fields if any
                for i, v in enumerate(lst):
                    if isinstance(v, str):
                        lst[i] = scrub_visible_reply(v)
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict) and item.get("role") == "assistant" and isinstance(item.get("content"), str):
                                item["content"] = scrub_visible_reply(item["content"])
                return tuple(lst)
        except Exception:
            pass
        return out

# === BRAIN STAGE 3 OVERLAY END ===



# ===========================
# BRAIN STAGE 4 OVERLAY
# ===========================
try:
    from brain import selfstate_router as _brain_stage4_self
    from brain import output_guard as _brain_stage4_guard
    from brain import initiative_sanity as _brain_stage4_init
    from brain import camera_truth as _brain_stage4_cam
    from brain import health_runtime as _brain_stage4_health

    _brain_stage4_health.print_startup_selftest(globals())

    if 'process_ava_action_blocks' in globals():
        _orig_process_ava_action_blocks_stage4 = process_ava_action_blocks
        def process_ava_action_blocks(reply_text, person_id):
            cleaned, actions = _orig_process_ava_action_blocks_stage4(reply_text, person_id)
            return _brain_stage4_guard.scrub_visible_reply(cleaned), actions

    if 'run_ava' in globals():
        _orig_run_ava_stage4 = run_ava
        def run_ava(user_input: str, image=None, active_person_id=None):
            if _brain_stage4_self.is_selfstate_query(user_input):
                if active_person_id is None and 'get_active_person_id' in globals():
                    active_person_id = get_active_person_id()
                active_profile = load_profile_by_id(active_person_id) if 'load_profile_by_id' in globals() else {'person_id': active_person_id or 'unknown', 'name': active_person_id or 'Unknown'}
                face_status = detect_face(image) if 'detect_face' in globals() else 'unknown'
                recognized_text = ''
                if 'recognize_face' in globals():
                    _rec = recognize_face(image)
                    if isinstance(_rec, tuple) and _rec:
                        recognized_text = _rec[0]
                visual = {'face_status': face_status, 'recognized_text': recognized_text}
                reply = _brain_stage4_self.build_selfstate_reply(globals(), user_input, image, active_profile)
                reply = _brain_stage4_guard.scrub_visible_reply(reply)
                actions = []
                try:
                    log_chat("user", user_input, {"person_id": active_profile.get("person_id"), "person_name": active_profile.get("name")})
                    log_chat("assistant", reply, {"person_id": active_profile.get("person_id"), "person_name": active_profile.get("name"), "actions": actions})
                except Exception:
                    pass
                try:
                    maybe_autoremember(user_input, reply, active_profile.get("person_id"))
                except Exception:
                    pass
                try:
                    reflection = reflect_on_last_reply(user_input, reply, active_profile.get("person_id"), actions=actions)
                except Exception:
                    reflection = {}
                return reply, visual, active_profile, actions, reflection
            reply, visual, active_profile, actions, reflection = _orig_run_ava_stage4(user_input, image, active_person_id)
            if isinstance(reply, str):
                reply = _brain_stage4_guard.scrub_visible_reply(reply)
            return reply, visual, active_profile, actions, reflection

    if 'chat_fn' in globals():
        _orig_chat_fn_stage4 = chat_fn
        def chat_fn(*args, **kwargs):
            result = _orig_chat_fn_stage4(*args, **kwargs)
            return _brain_stage4_guard.scrub_chat_callback_result(result)

    if 'voice_fn' in globals():
        _orig_voice_fn_stage4 = voice_fn
        def voice_fn(*args, **kwargs):
            result = _orig_voice_fn_stage4(*args, **kwargs)
            return _brain_stage4_guard.scrub_chat_callback_result(result)

    if 'detect_face' in globals():
        _orig_detect_face_stage4 = detect_face
        def detect_face(image):
            live = image
            if live is None:
                try:
                    live = _brain_stage4_cam.read_live_frame()
                except Exception:
                    live = image
            return _orig_detect_face_stage4(live)

    if 'recognize_face' in globals():
        _orig_recognize_face_stage4 = recognize_face
        def recognize_face(image):
            live = image
            if live is None:
                try:
                    live = _brain_stage4_cam.read_live_frame()
                except Exception:
                    live = image
            return _orig_recognize_face_stage4(live)

    if 'choose_initiative_candidate' in globals():
        _orig_choose_initiative_candidate_stage4 = choose_initiative_candidate
        def choose_initiative_candidate(*args, **kwargs):
            result = _orig_choose_initiative_candidate_stage4(*args, **kwargs)
            return _brain_stage4_init.sanitize_candidate_result(result, globals())

    print("[brain-stage4] overlay loaded")
except Exception as _brain_stage4_e:
    print(f"[brain-stage4] overlay failed: {_brain_stage4_e}")




# === BRAIN_STAGE5_OVERLAY_BEGIN ===
try:
    from brain.profile_manager import (
        sanitize_active_person,
        resolve_profile_key_from_text,
        merge_profiles,
        delete_profile,
        maybe_add_alias,
        protected_profile_match,
        ensure_alias_map,
        normalize_person_key,
    )
    from brain.identity_resolver import resolve_confirmed_identity
    from brain.camera_truth import build_camera_truth, camera_identity_reply
    from brain.initiative_sanity import desaturate_candidate_scores
    from brain.output_guard import scrub_visible_reply
    print("[brain-stage5] overlay loaded")
except Exception as _brain_stage5_exc:
    print("[brain-stage5] overlay failed:", _brain_stage5_exc)

def stage5_apply_profile_safety():
    try:
        global active_person, profiles
        if isinstance(globals().get("profiles"), dict):
            for _k, _p in list(profiles.items()):
                try:
                    ensure_alias_map(_p)
                except Exception:
                    pass
            active_person = sanitize_active_person(globals().get("active_person"), profiles, fallback="zeke")
    except Exception as e:
        print("[brain-stage5] profile safety error:", e)

def stage5_resolve_identity_claim(user_text):
    try:
        global profiles, active_person
        if not isinstance(globals().get("profiles"), dict):
            return None
        resolved, debug = resolve_confirmed_identity(user_text, profiles, globals().get("active_person"))
        if resolved:
            active_person = sanitize_active_person(resolved, profiles, fallback="zeke")
            print("[brain-stage5] identity resolved:", debug)
        return resolved
    except Exception as e:
        print("[brain-stage5] identity resolve error:", e)
        return None

def stage5_safe_visible_reply(text):
    try:
        return scrub_visible_reply(text)
    except Exception:
        return text

def stage5_sanitize_candidates(candidates):
    try:
        return desaturate_candidate_scores(candidates)
    except Exception:
        return candidates

stage5_apply_profile_safety()
# === BRAIN_STAGE5_OVERLAY_END ===




# ===========================
# BRAIN STAGE 6 OVERLAY
# ===========================
try:
    import re as _brain_stage6_re
    from brain import output_guard as _brain_stage6_guard
    from brain import selfstate_router as _brain_stage6_self
    from brain import health_runtime as _brain_stage6_health
    from brain import profile_manager as _brain_stage6_profiles
    from brain import identity_resolver as _brain_stage6_identity
    from brain import initiative_sanity as _brain_stage6_init
    from brain import memory_reader as _brain_stage6_mem
    from brain import camera_live as _brain_stage6_live
    from brain import camera_truth as _brain_stage6_camtruth

    _brain_stage6_health.print_startup_selftest(globals())

    def _brain_stage6_list_profile_map():
        out = {}
        if 'list_profiles' in globals():
            try:
                for p in list_profiles() or []:
                    if isinstance(p, dict):
                        pid = p.get('person_id')
                        if pid:
                            out[pid] = p
            except Exception:
                pass
        return out

    if 'create_or_get_profile' in globals():
        _orig_create_or_get_profile_stage6 = create_or_get_profile
        def create_or_get_profile(name: str, relationship_to_zeke: str = "known person", allowed: bool = True):
            cleaned = (name or '').strip()
            if not _brain_stage6_profiles.is_valid_profile_name(cleaned):
                if 'load_profile_by_id' in globals() and 'OWNER_PERSON_ID' in globals():
                    return load_profile_by_id(OWNER_PERSON_ID)
                return _orig_create_or_get_profile_stage6('Unknown', relationship_to_zeke, allowed)
            profile = _orig_create_or_get_profile_stage6(cleaned, relationship_to_zeke, allowed)
            try:
                profile = _brain_stage6_profiles.ensure_aliases_in_profile(profile)
                if 'save_profile' in globals():
                    save_profile(profile)
            except Exception:
                pass
            return profile

    if 'infer_person_from_text' in globals():
        _orig_infer_person_from_text_stage6 = infer_person_from_text
        def infer_person_from_text(user_input: str, current_person_id: str):
            profiles = _brain_stage6_list_profile_map()
            resolved, debug = _brain_stage6_identity.resolve_confirmed_identity(user_input, profiles, current_person_id)
            if resolved:
                return resolved, f"stage6_identity:{debug.get('reason')}"
            low = (user_input or '').strip().lower()
            alias_match = _brain_stage6_profiles.resolve_profile_key_from_text(low, profiles)
            if alias_match:
                return alias_match, 'stage6_alias_resolution'
            pid, source = _orig_infer_person_from_text_stage6(user_input, current_person_id)
            if pid and _brain_stage6_profiles.looks_like_phrase_profile(pid.replace('_', ' ')):
                return current_person_id, 'stage6_rejected_phrase_profile'
            return pid, source

    if 'set_active_person' in globals():
        _orig_set_active_person_stage6 = set_active_person
        def set_active_person(person_id: str, source: str = 'manual'):
            safe_person_id = person_id
            if _brain_stage6_profiles.looks_like_phrase_profile(str(person_id).replace('_', ' ')):
                if 'OWNER_PERSON_ID' in globals():
                    safe_person_id = OWNER_PERSON_ID
            profile = _orig_set_active_person_stage6(safe_person_id, source)
            try:
                profile = _brain_stage6_profiles.ensure_aliases_in_profile(profile)
                if 'save_profile' in globals():
                    save_profile(profile)
            except Exception:
                pass
            return profile

    if 'choose_initiative_candidate' in globals():
        _orig_choose_initiative_candidate_stage6 = choose_initiative_candidate
        def choose_initiative_candidate(*args, **kwargs):
            result = _orig_choose_initiative_candidate_stage6(*args, **kwargs)
            return _brain_stage6_init.sanitize_candidate_result(result, globals())

    if 'process_ava_action_blocks' in globals():
        _orig_process_ava_action_blocks_stage6 = process_ava_action_blocks
        def process_ava_action_blocks(reply_text, person_id):
            cleaned, actions = _orig_process_ava_action_blocks_stage6(reply_text, person_id)
            return _brain_stage6_guard.scrub_visible_reply(cleaned), actions

    if 'build_prompt' in globals():
        _orig_build_prompt_stage6 = build_prompt
        def build_prompt(user_input: str, image=None, active_person_id: str | None = None):
            active_id = active_person_id
            if active_id is None and 'get_active_person_id' in globals():
                active_id = get_active_person_id()
            profiles = _brain_stage6_list_profile_map()
            resolved, debug = _brain_stage6_identity.resolve_confirmed_identity(user_input, profiles, active_id)
            if resolved:
                active_id = resolved
                try:
                    if 'set_active_person' in globals():
                        set_active_person(active_id, source='stage6_identity_resolution')
                except Exception:
                    pass
            messages, visual, active_profile = _orig_build_prompt_stage6(user_input, image=image, active_person_id=active_id)
            try:
                if isinstance(active_profile, dict):
                    active_profile = _brain_stage6_profiles.ensure_aliases_in_profile(active_profile)
                    if 'save_profile' in globals():
                        save_profile(active_profile)
            except Exception:
                pass
            try:
                dynamic_summary = _brain_stage6_mem.build_memory_reader_summary(globals(), user_input, active_profile)
                if messages and hasattr(messages[-1], 'content') and isinstance(messages[-1].content, str):
                    messages[-1].content += "\n\n" + dynamic_summary
            except Exception as _e:
                print(f"[brain-stage6] memory reader append failed: {_e}")
            return messages, visual, active_profile

    if 'run_ava' in globals():
        _orig_run_ava_stage6 = run_ava
        def run_ava(user_input: str, image=None, active_person_id=None):
            live_image = image
            if live_image is None:
                try:
                    live_image = _brain_stage6_live.read_live_frame()
                except Exception:
                    live_image = image
            if _brain_stage6_self.is_selfstate_query(user_input):
                if active_person_id is None and 'get_active_person_id' in globals():
                    active_person_id = get_active_person_id()
                active_profile = load_profile_by_id(active_person_id) if 'load_profile_by_id' in globals() else {'person_id': active_person_id or 'unknown', 'name': active_person_id or 'Unknown'}
                reply = _brain_stage6_self.build_selfstate_reply(globals(), user_input, live_image, active_profile)
                reply = _brain_stage6_guard.scrub_visible_reply(reply)
                actions = []
                try:
                    log_chat('user', user_input, {'person_id': active_profile.get('person_id'), 'person_name': active_profile.get('name')})
                    log_chat('assistant', reply, {'person_id': active_profile.get('person_id'), 'person_name': active_profile.get('name'), 'actions': actions})
                except Exception:
                    pass
                reflection = {}
                try:
                    maybe_autoremember(user_input, reply, active_profile.get('person_id'))
                    reflection = reflect_on_last_reply(user_input, reply, active_profile.get('person_id'), actions=actions)
                except Exception:
                    reflection = {}
                visual = {
                    'face_status': detect_face(live_image) if 'detect_face' in globals() else 'unknown',
                    'recognition_status': recognize_face(live_image)[0] if 'recognize_face' in globals() else 'unknown',
                    'memory_preview': 'self-state-check'
                }
                return reply, visual, active_profile, actions, reflection
            reply, visual, active_profile, actions, reflection = _orig_run_ava_stage6(user_input, live_image, active_person_id)
            if isinstance(reply, str):
                reply = _brain_stage6_guard.scrub_visible_reply(reply)
            return reply, visual, active_profile, actions, reflection

    if 'chat_fn' in globals():
        _orig_chat_fn_stage6 = chat_fn
        def chat_fn(message, history, image):
            result = _orig_chat_fn_stage6(message, history, image)
            return _brain_stage6_guard.scrub_chat_callback_result(result)

    if 'camera_tick_fn' in globals():
        _orig_camera_tick_fn_stage6 = camera_tick_fn
        _HF_FACE_WAS_PRESENT = [False]

        def camera_tick_fn(image):
            live_image = image
            if live_image is None:
                try:
                    live_image = _brain_stage6_live.read_live_frame()
                except Exception:
                    live_image = image

            face_now = detect_face(live_image) == "Face detected"
            face_was = _HF_FACE_WAS_PRESENT[0]
            _HF_FACE_WAS_PRESENT[0] = face_now

            result = list(_orig_camera_tick_fn_stage6(live_image))

            if face_was and not face_now:
                current = _get_canonical_history()
                alert = {"role": "assistant", "content": "I notice the camera just went dark. Did you step away?"}
                result[0] = _set_canonical_history(list(current) + [alert])
                print("[camera] face-gone detected")

            return tuple(result)

    print('[brain-stage6] overlay loaded')
except Exception as _brain_stage6_error:
    print(f'[brain-stage6] overlay failed: {_brain_stage6_error}')




# ===========================
# BRAIN STAGE 6.1 OVERLAY
# ===========================
try:
    from brain import initiative_sanity as _brain_stage6_1_init
    from brain import memory_reader as _brain_stage6_1_mem

    if 'choose_initiative_candidate' in globals():
        _orig_choose_initiative_candidate_stage6_1 = choose_initiative_candidate
        def choose_initiative_candidate(*args, **kwargs):
            try:
                new_args, new_kwargs, did_desaturate = _brain_stage6_1_init.maybe_desaturate_args(args, kwargs)
                if did_desaturate:
                    print('[brain-stage6.1] candidate desaturation applied before selection')
                else:
                    print('[brain-stage6.1] no candidate list found to desaturate before selection')
                result = _orig_choose_initiative_candidate_stage6_1(*new_args, **new_kwargs)
            except Exception as _e:
                print(f'[brain-stage6.1] pre-selection desaturation failed: {_e}')
                result = _orig_choose_initiative_candidate_stage6_1(*args, **kwargs)
            return _brain_stage6_1_init.sanitize_candidate_result(result, globals())

    if 'build_prompt' in globals():
        _orig_build_prompt_stage6_1 = build_prompt
        def build_prompt(user_input: str, image=None, active_person_id: str | None = None):
            messages, visual, active_profile = _orig_build_prompt_stage6_1(user_input, image=image, active_person_id=active_person_id)
            try:
                dynamic_summary = _brain_stage6_1_mem.build_memory_reader_summary(globals(), user_input, active_profile)
                if messages and hasattr(messages[-1], 'content') and isinstance(messages[-1].content, str):
                    marker = 'DYNAMIC SELF / MEMORY READER:'
                    if marker in messages[-1].content:
                        head = messages[-1].content.split(marker)[0].rstrip()
                        messages[-1].content = head + '\n\n' + dynamic_summary
                    else:
                        messages[-1].content += '\n\n' + dynamic_summary
            except Exception as _e:
                print(f'[brain-stage6.1] memory reader refresh failed: {_e}')
            return messages, visual, active_profile

    print('[brain-stage6.1] overlay loaded')
except Exception as _brain_stage6_1_error:
    print(f'[brain-stage6.1] overlay failed: {_brain_stage6_1_error}')




# ===========================
# BRAIN STAGE 7 OVERLAY
# ===========================
try:
    from brain import trust_manager     as _brain_stage7_trust
    from brain import persona_switcher  as _brain_stage7_persona
    from brain import profile_store     as _brain_stage7_store
    from brain import identity_loader   as _brain_stage7_identity

    # ── Startup ──────────────────────────────────────────────────────────────
    _brain_stage7_store.seed_default_profiles()
    _brain_stage7_identity.ensure_identity_files()
    _ava_identity_block = _brain_stage7_identity.load_ava_identity()
    print("[brain-stage7] identity loaded")
    print("[brain-stage7] default profiles seeded")

    # ── Helper: resolve profile using stage7 store ───────────────────────────
    def _stage7_get_profile(person_id):
        if not person_id:
            return {}
        p = _brain_stage7_store.load_profile(person_id)
        if p:
            return p
        # Fall back to legacy loader if available
        if 'load_profile_by_id' in globals():
            legacy = load_profile_by_id(person_id)
            if legacy and isinstance(legacy, dict):
                return legacy
        return {"person_id": person_id, "name": person_id, "trust_level": 2}

    # ── Patch: create_or_get_profile ─────────────────────────────────────────
    if 'create_or_get_profile' in globals():
        _orig_create_or_get_profile_s7 = create_or_get_profile
        def create_or_get_profile(name: str, relationship_to_zeke: str = "known person", allowed: bool = True):
            from brain.profile_manager import is_valid_profile_name, normalize_person_key
            cleaned = (name or '').strip()
            if not is_valid_profile_name(cleaned):
                return _stage7_get_profile(globals().get('OWNER_PERSON_ID') or 'zeke')
            person_id = normalize_person_key(cleaned)
            profile = _brain_stage7_store.get_or_create_profile(
                person_id, name=cleaned, relationship=relationship_to_zeke
            )
            return profile

    # ── Patch: build_prompt ───────────────────────────────────────────────────
    if 'build_prompt' in globals():
        _orig_build_prompt_s7 = build_prompt
        def build_prompt(user_input: str, image=None, active_person_id=None):
            active_id = active_person_id
            if active_id is None and 'get_active_person_id' in globals():
                active_id = get_active_person_id()

            active_profile = _stage7_get_profile(active_id)

            # Touch last-seen timestamp
            if active_id:
                try:
                    _brain_stage7_store.touch_last_seen(active_id)
                except Exception:
                    pass

            messages, visual, orig_profile = _orig_build_prompt_s7(
                user_input, image=image, active_person_id=active_id
            )

            # Use stage7 profile if richer, otherwise use original
            merged_profile = active_profile if active_profile else (orig_profile or {})

            # Build persona block for this person
            try:
                persona_block = _brain_stage7_persona.build_persona_block(merged_profile)
                trust_note    = _brain_stage7_trust.build_trust_context_note(merged_profile)
            except Exception as _pe:
                print(f"[brain-stage7] persona build failed: {_pe}")
                persona_block = ""
                trust_note    = ""

            # Inject identity + persona into the first system message
            try:
                identity_block = _ava_identity_block
                injected = f"{identity_block}\n\n{persona_block}\n\n{trust_note}"
                if messages:
                    # Find existing system message or prepend one
                    if hasattr(messages[0], 'role') and messages[0].role == 'system':
                        messages[0].content = injected + "\n\n" + messages[0].content
                    else:
                        from langchain_core.messages import SystemMessage
                        messages.insert(0, SystemMessage(content=injected))
            except Exception as _ie:
                print(f"[brain-stage7] identity inject failed: {_ie}")

            return messages, visual, merged_profile

    # ── Patch: run_ava — trust gate + deflection ──────────────────────────────
    if 'run_ava' in globals():
        _orig_run_ava_s7 = run_ava
        def run_ava(user_input: str, image=None, active_person_id=None):
            active_id = active_person_id
            if active_id is None and 'get_active_person_id' in globals():
                active_id = get_active_person_id()

            active_profile = _stage7_get_profile(active_id)

            # Blocked check
            if _brain_stage7_trust.is_blocked(active_profile):
                reply = _brain_stage7_persona.get_blocked_reply()
                print(f"[brain-stage7] blocked user intercepted: {active_id}")
                return reply, {}, active_profile, [], {}

            # Deflection check (stranger asking sensitive questions)
            if _brain_stage7_persona.should_deflect(active_profile, user_input):
                reply = _brain_stage7_persona.get_deflect_reply(active_profile, user_input)
                print(f"[brain-stage7] deflected sensitive query from trust={_brain_stage7_trust.get_trust_level(active_profile)}")
                return reply, {}, active_profile, [], {}

            # Run normal pipeline
            result = _orig_run_ava_s7(user_input, image, active_id)
            reply = result[0] if result else ""

            # Process any IDENTITY action blocks in reply
            if isinstance(reply, str):
                reply = _brain_stage7_identity.process_identity_actions(reply)
                result = (reply,) + result[1:]

            return result

    # ── Patch: reflect_on_last_reply — auto-learn about this person ───────────
    if 'reflect_on_last_reply' in globals():
        _orig_reflect_s7 = reflect_on_last_reply
        def reflect_on_last_reply(user_input: str, reply: str, person_id: str, actions=None):
            reflection = _orig_reflect_s7(user_input, reply, person_id, actions=actions)

            # If Ava learned something, append to profile notes
            try:
                learned = None
                if isinstance(reflection, dict):
                    learned = reflection.get("learned_fact") or reflection.get("new_fact")
                if learned and person_id:
                    _brain_stage7_store.update_profile_notes(person_id, str(learned))
                    print(f"[brain-stage7] learned fact saved to profile: {person_id}")
                # Always update last topic if we have it
                if person_id:
                    topic = (user_input or "")[:120]
                    _brain_stage7_store.touch_last_seen(person_id, topic)
            except Exception as _re:
                print(f"[brain-stage7] profile auto-learn failed: {_re}")

            # If talking to Ezekiel (owner), also update USER.md
            try:
                if person_id and _brain_stage7_trust.is_owner(_stage7_get_profile(person_id)):
                    if isinstance(reflection, dict) and reflection.get("learned_fact"):
                        _brain_stage7_identity.append_to_user_file(reflection["learned_fact"])
            except Exception:
                pass

            return reflection

    # ── Handle new stranger → auto-create profile ────────────────────────────
    if 'infer_person_from_text' in globals():
        _orig_infer_s7 = infer_person_from_text
        def infer_person_from_text(user_input: str, current_person_id: str):
            pid, source = _orig_infer_s7(user_input, current_person_id)
            if pid and pid != current_person_id:
                # Make sure a profile exists for this newly identified person
                if not _brain_stage7_store.load_profile(pid):
                    _brain_stage7_store.get_or_create_profile(
                        pid, trust_level=2
                    )
                    print(f"[brain-stage7] auto-created stranger profile: {pid}")
            return pid, source

    print("[brain-stage7] overlay loaded")

except Exception as _brain_stage7_error:
    import traceback
    print(f"[brain-stage7] overlay failed: {_brain_stage7_error}")
    traceback.print_exc()




# ===========================
