from pathlib import Path

TARGET = Path("avaagent.py")
PATCH = """
# ===========================
# BRAIN STAGE 6.2 OVERLAY
# ===========================
try:
    from brain import initiative_sanity as _brain_stage6_2_init
    from brain import memory_reader as _brain_stage6_2_mem

    if 'collect_initiative_candidates' in globals():
        _orig_collect_initiative_candidates_stage6_2 = collect_initiative_candidates
        def collect_initiative_candidates(*args, **kwargs):
            candidates = _orig_collect_initiative_candidates_stage6_2(*args, **kwargs)
            try:
                desaturated = _brain_stage6_2_init.desaturate_candidate_scores(candidates)
                print('[brain-stage6.2] candidate desaturation applied before selection')
                return desaturated
            except Exception as _e:
                print(f'[brain-stage6.2] candidate desaturation failed: {_e}')
                return candidates

    if 'choose_initiative_candidate' in globals():
        _orig_choose_initiative_candidate_stage6_2 = choose_initiative_candidate
        def choose_initiative_candidate(*args, **kwargs):
            result = _orig_choose_initiative_candidate_stage6_2(*args, **kwargs)
            return _brain_stage6_2_init.sanitize_candidate_result(result, globals())

    if 'build_prompt' in globals():
        _orig_build_prompt_stage6_2 = build_prompt
        def build_prompt(user_input: str, image=None, active_person_id=None):
            messages, visual, active_profile = _orig_build_prompt_stage6_2(
                user_input, image=image, active_person_id=active_person_id
            )
            try:
                dynamic_summary = _brain_stage6_2_mem.build_memory_reader_summary(
                    globals(), user_input, active_profile
                )
                if messages and hasattr(messages[-1], 'content') and isinstance(messages[-1].content, str):
                    marker = 'DYNAMIC SELF / MEMORY READER:'
                    if marker in messages[-1].content:
                        head = messages[-1].content.split(marker)[0].rstrip()
                        messages[-1].content = head + '\\n\\n' + dynamic_summary
                    else:
                        messages[-1].content += '\\n\\n' + dynamic_summary
            except Exception as _e:
                print(f'[brain-stage6.2] memory reader refresh failed: {_e}')
            return messages, visual, active_profile

    print('[brain-stage6.2] overlay loaded')
except Exception as _brain_stage6_2_error:
    print(f'[brain-stage6.2] overlay failed: {_brain_stage6_2_error}')
"""

text = TARGET.read_text(encoding="utf-8")
marker = "# ===========================\n# BRAIN STAGE 6.2 OVERLAY\n# ==========================="
if marker in text:
    start = text.index(marker)
    text = text[:start].rstrip() + "\n\n" + PATCH.strip() + "\n"
else:
    text = text.rstrip() + "\n\n" + PATCH.strip() + "\n"

TARGET.write_text(text, encoding="utf-8")
print("Applied stage 6.2 overlay to avaagent.py")
