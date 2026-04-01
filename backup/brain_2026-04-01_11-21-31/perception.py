from __future__ import annotations
from .shared import now_iso

def load_camera_state(host):
    orig = host.get('_BRAIN_ORIG_LOAD_CAMERA_STATE')
    if callable(orig):
        try: return dict(orig() or {})
        except Exception: pass
    return {'time': now_iso(), 'status': 'unknown'}

def save_camera_state(host, state):
    orig = host.get('_BRAIN_ORIG_SAVE_CAMERA_STATE')
    if callable(orig):
        return orig(state)
    return None

def process_camera_snapshot(host, *args, **kwargs):
    # Bridge wrapper: keep live snapshot analysis in the existing Ava core,
    # but route the active callable through brain/perception.py so the brain
    # folder owns the perception entry point for future refactors.
    orig = host.get('_BRAIN_ORIG_PROCESS_CAMERA_SNAPSHOT')
    if callable(orig):
        return orig(*args, **kwargs)
    raise RuntimeError('Original process_camera_snapshot is unavailable')
