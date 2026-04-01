def print_startup_selftest(g: dict):
    checks = []
    checks.append(("vector_memory", bool(g.get("vectorstore") is not None)))
    checks.append(("mood_path", bool(g.get("MOOD_PATH"))))
    checks.append(("personality_path", bool(g.get("PERSONALITY_PATH"))))
    checks.append(("face_model_loader", callable(g.get("load_face_model_if_available"))))
    ok = sum(1 for _, state in checks if state)
    total = len(checks)
    status = "HEALTHY" if ok == total else "DEGRADED"
    parts = ", ".join(f"{name}={'ok' if state else 'missing'}" for name, state in checks)
    print(f"[startup-selftest-stage6] {status} :: {parts}")
