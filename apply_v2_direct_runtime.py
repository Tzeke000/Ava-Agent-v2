from pathlib import Path

TARGET = Path("avaagent.py")

DIRECT_BLOCK = """
# ===========================
# V2 DIRECT RUNTIME
# ===========================
try:
    from brain.output_guard import scrub_visible_reply as _v2_scrub_visible_reply
    from brain.output_guard import scrub_chat_callback_result as _v2_scrub_chat_result
    from brain.memory_reader import build_memory_reader_summary as _v2_build_memory_reader_summary
    from brain.initiative_sanity import desaturate_candidate_scores as _v2_desaturate_candidate_scores
    from brain.initiative_sanity import sanitize_candidate_result as _v2_sanitize_candidate_result

    _v2_orig_collect_initiative_candidates = collect_initiative_candidates
    def collect_initiative_candidates(person_id: str):
        candidates = _v2_orig_collect_initiative_candidates(person_id)
        try:
            candidates = _v2_desaturate_candidate_scores(candidates)
            print("[v2-direct] candidate desaturation applied before selection")
        except Exception as _e:
            print(f"[v2-direct] candidate desaturation failed: {_e}")
        return candidates

    _v2_orig_choose_initiative_candidate = choose_initiative_candidate
    def choose_initiative_candidate(person_id: str, expression_state: dict | None = None):
        result = _v2_orig_choose_initiative_candidate(person_id, expression_state=expression_state)
        try:
            result = _v2_sanitize_candidate_result(result, globals())
        except Exception as _e:
            print(f"[v2-direct] candidate result sanitize failed: {_e}")
        return result

    _v2_orig_build_prompt = build_prompt
    def build_prompt(user_input: str, image=None, active_person_id=None):
        messages, visual, active_profile = _v2_orig_build_prompt(
            user_input, image=image, active_person_id=active_person_id
        )
        try:
            dynamic_summary = _v2_build_memory_reader_summary(globals(), user_input, active_profile)
            if messages and hasattr(messages[-1], "content") and isinstance(messages[-1].content, str):
                marker = "DYNAMIC SELF / MEMORY READER:"
                if marker in messages[-1].content:
                    head = messages[-1].content.split(marker)[0].rstrip()
                    messages[-1].content = head + "\\n\\n" + dynamic_summary
                else:
                    messages[-1].content += "\\n\\n" + dynamic_summary
        except Exception as _e:
            print(f"[v2-direct] memory reader append failed: {_e}")
        return messages, visual, active_profile

    if 'process_ava_action_blocks' in globals():
        _v2_orig_process_ava_action_blocks = process_ava_action_blocks
        def process_ava_action_blocks(reply_text, person_id):
            cleaned, actions = _v2_orig_process_ava_action_blocks(reply_text, person_id)
            return _v2_scrub_visible_reply(cleaned), actions

    if 'chat_fn' in globals():
        _v2_orig_chat_fn = chat_fn
        def chat_fn(*args, **kwargs):
            result = _v2_orig_chat_fn(*args, **kwargs)
            return _v2_scrub_chat_result(result)

    if 'run_ava' in globals():
        _v2_orig_run_ava = run_ava
        def run_ava(*args, **kwargs):
            result = _v2_orig_run_ava(*args, **kwargs)
            if isinstance(result, str):
                return _v2_scrub_visible_reply(result)
            return result

    print("[v2-direct] runtime loaded")
except Exception as _v2_direct_error:
    print(f"[v2-direct] runtime failed: {_v2_direct_error}")
"""

text = TARGET.read_text(encoding="utf-8", errors="ignore")

overlay_markers = [
    "# === BRAIN_STAGE5_OVERLAY_BEGIN ===",
    "# ===========================\n# BRAIN STAGE 6 OVERLAY",
    "# ===========================\n# BRAIN STAGE 6.1 OVERLAY",
    "# ===========================\n# BRAIN STAGE 7 OVERLAY",
    "# ===========================\n# BRAIN STAGE 6.2 OVERLAY",
    "# ===========================\n# V2 DIRECT RUNTIME"
]

cut_positions = [text.find(m) for m in overlay_markers if text.find(m) != -1]
if cut_positions:
    text = text[:min(cut_positions)].rstrip() + "\n\n"

text += DIRECT_BLOCK.strip() + "\n"
TARGET.write_text(text, encoding="utf-8")
print("Applied v2 direct runtime to avaagent.py")