"""
brain/gradio_ui.py — Gradio interface construction.

Extracted from avaagent.py. Call build_gradio_demo(callbacks) to
get the gr.Blocks demo object. All callback functions and UI-time
constants come in through the callbacks dict.
"""
from __future__ import annotations

from typing import Any


def build_gradio_demo(cbs: dict[str, Any]):
    """
    Build and return the Gradio Blocks demo.
    cbs must contain all callback functions and display constants used by the UI.
    """
    import gradio as gr

    chat_fn = cbs["chat_fn"]
    voice_fn = cbs["voice_fn"]
    camera_tick_fn = cbs["camera_tick_fn"]
    debug_panel_refresh_fn = cbs["debug_panel_refresh_fn"]
    refresh_profiles_fn = cbs["refresh_profiles_fn"]
    create_profile_fn = cbs["create_profile_fn"]
    switch_profile_fn = cbs["switch_profile_fn"]
    save_note_fn = cbs["save_note_fn"]
    save_like_fn = cbs["save_like_fn"]
    save_impression_fn = cbs["save_impression_fn"]
    memory_search_fn = cbs["memory_search_fn"]
    memory_delete_fn = cbs["memory_delete_fn"]
    memory_manual_add_fn = cbs["memory_manual_add_fn"]
    memory_update_importance_fn = cbs["memory_update_importance_fn"]
    memory_refresh_recent_fn = cbs["memory_refresh_recent_fn"]
    workbench_refresh_index_fn = cbs["workbench_refresh_index_fn"]
    workbench_read_fn = cbs["workbench_read_fn"]
    workbench_write_fn = cbs["workbench_write_fn"]
    workbench_append_fn = cbs["workbench_append_fn"]
    read_chatlog_fn = cbs["read_chatlog_fn"]
    read_code_fn = cbs["read_code_fn"]
    reload_personality_fn = cbs["reload_personality_fn"]
    capture_face_for_active_person_fn = cbs["capture_face_for_active_person_fn"]
    train_faces_fn = cbs["train_faces_fn"]
    recognize_face_now_fn = cbs["recognize_face_now_fn"]
    refresh_reflections_fn = cbs["refresh_reflections_fn"]
    refresh_self_model_fn = cbs["refresh_self_model_fn"]

    CAMERA_TICK_SECONDS = float(cbs.get("CAMERA_TICK_SECONDS", 5.0))
    get_profile_choices = cbs["get_profile_choices"]
    get_active_profile_text = cbs["get_active_profile_text"]
    get_active_profile_summary = cbs["get_active_profile_summary"]

    with gr.Blocks(title="Ava — v2") as demo:
        gr.Markdown("# Ava\nv2 — modular brain with persistent memory, self-reflection, and workspace.")

        camera_timer = gr.Timer(value=CAMERA_TICK_SECONDS, active=True)

        with gr.Row():
            with gr.Column(scale=2):
                try:
                    chatbot = gr.Chatbot(label="Conversation with Ava", height=500, type="messages")
                except TypeError:
                    chatbot = gr.Chatbot(label="Conversation with Ava", height=500)
                msg = gr.Textbox(label="Type a message", placeholder="Hey Ava...")
                voice_input = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Speak to Ava")
            with gr.Column(scale=1):
                camera = gr.Image(sources=["webcam"], streaming=True, type="numpy", label="Live Camera")
                latest_snapshot_image = gr.Image(label="Latest Analyzed Snapshot", type="numpy")
                face_status = gr.Textbox(label="Face Status", value="No camera image")
                recognition_status = gr.Textbox(label="Recognition Status", value="Face model not trained")
                expression_status = gr.Textbox(label="Expression Status")
                camera_memory_status = gr.Textbox(label="Camera Memory Status", lines=4)
                recent_camera_events_box = gr.Textbox(label="Recent Camera Events", lines=8)
                memory_status = gr.Textbox(label="Memory Status")
                mood_status = gr.Textbox(label="Current Mood")
                blend_status = gr.Textbox(label="Emotion Blend")
                time_status = gr.Textbox(label="Time Sense")
                active_person_status = gr.Textbox(label="Active Person")

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
                initiative_status = gr.Textbox(label="Autonomous Initiative", lines=3)

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
            memory_view = gr.Textbox(label="Recent / Search Memory View", lines=16)
            reflection_view = gr.Textbox(label="Recent Self Reflections", lines=16)

        with gr.Row():
            self_model_view = gr.Textbox(label="Ava Self Model", lines=18)
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
                workbench_index_view = gr.Textbox(label="Workbench Index", lines=20)
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

        with gr.Accordion("Development debug panel", open=False):
            dbg_refresh_btn = gr.Button("Refresh debug panel")
            with gr.Row():
                dbg_meta = gr.Textbox(label="Meta / mood state", lines=4)
                dbg_goal = gr.Textbox(label="Active operational goal", lines=4)
            with gr.Row():
                dbg_narrative = gr.Textbox(label="Self-narrative snapshot", lines=5)
                dbg_refl_health = gr.Textbox(label="Last reflection · health · relationship", lines=10)

        # ── event wiring ──
        _chat_outputs = [chatbot, msg, face_status, memory_status, mood_status, recognition_status, expression_status, blend_status, time_status, active_person_status, active_profile_json, memory_view, action_status, reflection_view, self_model_view, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box]
        msg.submit(chat_fn, inputs=[msg, chatbot, camera], outputs=_chat_outputs)
        voice_input.stop_recording(voice_fn, inputs=[voice_input, chatbot, camera], outputs=[chatbot, voice_input, face_status, memory_status, mood_status, recognition_status, expression_status, blend_status, time_status, active_person_status, active_profile_json, memory_view, action_status, reflection_view, self_model_view, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box])
        camera_timer.tick(camera_tick_fn, inputs=[camera, chatbot], outputs=[chatbot, face_status, recognition_status, expression_status, time_status, active_person_status, active_profile_json, initiative_status, latest_snapshot_image, camera_memory_status, recent_camera_events_box], show_progress="hidden", queue=False, trigger_mode="always_last", concurrency_limit=1)

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
        dbg_refresh_btn.click(debug_panel_refresh_fn, inputs=[], outputs=[dbg_meta, dbg_goal, dbg_narrative, dbg_refl_health])

    return demo
