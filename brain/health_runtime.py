def print_startup_selftest(g: dict):
    checks = {
        "vector_memory": "vectorstore" in g and g["vectorstore"] is not None,
        "mood_path": g.get("MOOD_PATH") is not None,
        "personality_path": g.get("PERSONALITY_PATH") is not None,
        "face_model_loader": "load_face_model_if_available" in g,
    }
    status = "OK" if all(checks.values()) else "DEGRADED"
    details = " | ".join(f"{k}={'ok' if v else 'missing'}" for k, v in checks.items())
    print(f"[startup-selftest-stage6] {status} :: {details}")
