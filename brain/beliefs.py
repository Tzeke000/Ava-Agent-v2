from __future__ import annotations
from .shared import clamp01, latest_user_text, jaccard, normalize_history

def build_belief_state(host, history=None, expression_state=None):
    history = normalize_history(history or [])
    user_text = latest_user_text(history).lower()
    top_belief = 'idle'
    conf = 0.25
    beliefs = []

    def add(name, confidence, evidence=None):
        nonlocal top_belief, conf
        beliefs.append({'name': name, 'confidence': round(clamp01(confidence),3), 'evidence': evidence or []})
        if confidence > conf:
            top_belief, conf = name, confidence

    if any(p in user_text for p in ['how are you feeling', 'are you okay', 'system status', 'self test', 'how is your memory']):
        add('user_requests_self_state', 0.92, ['self_state_query'])
    if any(p in user_text for p in ['can you see me', 'do you see me', 'how about now', 'who is at the camera']):
        add('user_seeks_visual_confirmation', 0.9, ['visual_query'])
    if any(p in user_text for p in ['don't worry', 'its ok', 'it's ok', 'nothing specific', 'not concerned']):
        add('topic_closed_or_softly_redirected', 0.82, ['soft_close'])
    if any(p in user_text for p in ['you keep repeating', 'repeating yourself']):
        add('user_reports_repetition', 0.88, ['repetition_report'])
    if not beliefs and user_text:
        add('latest_user_context', 0.55, ['recent_user_message'])
    return {
        'beliefs': beliefs,
        'top_belief': top_belief,
        'top_confidence': round(conf,3),
        'recent_user_text': user_text[:200],
    }
