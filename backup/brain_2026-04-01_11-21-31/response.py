from __future__ import annotations
import re
from .shared import extract_text

def scrub_visible_reply(text):
    t = str(text or '')
    t = re.sub(r'\(Active goal expression:[^\)]*\)', '', t, flags=re.I)
    t = re.sub(r'Active goal expression:[^
]*', '', t, flags=re.I)
    t = re.sub(r'Let the current operating goal shape[^
]*', '', t, flags=re.I)
    t = re.sub(r'
{3,}', '

', t).strip()
    return t

def generate_autonomous_message(host, *args, **kwargs):
    orig = host.get('_BRAIN_ORIG_GENERATE_AUTONOMOUS_MESSAGE')
    if not callable(orig):
        raise RuntimeError('Original generate_autonomous_message is unavailable')
    result = orig(*args, **kwargs)
    if isinstance(result, tuple) and result:
        first = scrub_visible_reply(result[0])
        return (first, *result[1:])
    if isinstance(result, str):
        return scrub_visible_reply(result)
    return result
