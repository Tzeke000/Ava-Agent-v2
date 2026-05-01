"""scripts/setup_virtual_audio.py — VB-CABLE A+B presence + smoketest.

Component 1 of the autonomous testing work order. The actual VB-CABLE
install requires admin privileges and a reboot, so this script does NOT
install — it verifies presence and routes a known tone end-to-end so we
can confirm the cables are correctly named and wired before driving the
full doctor harness.

Usage:
    py -3.11 scripts/setup_virtual_audio.py             # verify only
    py -3.11 scripts/setup_virtual_audio.py --tone-test # play 1s tone, capture, compare

Per docs/AUTONOMOUS_TESTING.md § Virtual audio cable setup.

Expected device names (case-insensitive substring match, since indices
renumber across reboots):

    Claude -> Ava direction:
      output: "CABLE Input"      (Claude plays here)
      input:  "CABLE Output"     (Ava records here as her mic)

    Ava -> Claude direction:
      output: "CABLE-A Input"    (Ava plays her TTS here)
      input:  "CABLE-A Output"   (Claude records here as his "ears")

If install is missing, prints concrete next steps (download URL, install
flow, reboot reminder).
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any


def _try_import_audio() -> tuple[Any, Any] | None:
    try:
        import sounddevice as sd  # type: ignore
        import numpy as np  # type: ignore
        return sd, np
    except Exception as e:
        print(f"[venv] sounddevice / numpy import failed: {e!r}")
        return None


def _find_device(sd, name_substr: str, kind: str) -> int | None:
    """Return device index whose name contains substr and has the right channel count."""
    target_key = f"max_{kind}_channels"
    name_lower = name_substr.lower()
    for i, dev in enumerate(sd.query_devices()):
        if name_lower in dev.get("name", "").lower() and dev.get(target_key, 0) > 0:
            return i
    return None


_NEEDED = [
    ("CABLE Input", "output", "Claude -> Ava (Claude's TTS plays here)"),
    ("CABLE Output", "input", "Claude -> Ava (Ava's mic records here)"),
    ("CABLE-A Input", "output", "Ava -> Claude (Ava's TTS plays here)"),
    ("CABLE-A Output", "input", "Ava -> Claude (Claude's STT records here)"),
]


def _print_install_help() -> None:
    print()
    print("VB-CABLE A+B not detected. Install steps:")
    print("  1. Download VB-CABLE driver pack:")
    print("     https://vb-audio.com/Cable/")
    print("     File: VBCABLE_Driver_Pack45.zip")
    print("  2. Right-click VBCABLE_Setup_x64.exe -> Run as administrator.")
    print("  3. Reboot.")
    print("  4. Donate $5 for the A+B pack at:")
    print("     https://shop.vb-audio.com/en/win-apps/12-vb-cable-ab.html")
    print("  5. Run VBCABLE_A_Setup_x64.exe and VBCABLE_B_Setup_x64.exe as admin.")
    print("  6. Reboot again.")
    print("  7. In Sound -> Recording, set each CABLE Output device's sample rate to")
    print("     48000 Hz, 16-bit, in its Properties -> Advanced tab.")
    print("  8. Re-run this script to verify presence.")
    print()


def verify_presence(sd) -> bool:
    print("Scanning for VB-CABLE A+B devices...")
    print()
    all_found = True
    for name, kind, role in _NEEDED:
        idx = _find_device(sd, name, kind)
        if idx is None:
            print(f"  [MISSING] {name} ({kind})  — {role}")
            all_found = False
        else:
            dev = sd.query_devices(idx)
            print(f"  [OK]      {name} ({kind})  index={idx}  rate={dev.get('default_samplerate', '?')}  — {role}")
    print()
    return all_found


def tone_test(sd, np_mod) -> bool:
    """Play a 1s 440Hz tone on CABLE Input, capture from CABLE Output, verify peak.

    This is the minimum end-to-end test: bytes Claude plays into the
    Claude->Ava cable should appear on the matching capture side.
    """
    print("Running tone test (1s @ 440Hz, CABLE Input -> CABLE Output)...")
    sample_rate = 48000
    duration = 1.0
    freq = 440.0
    t = np_mod.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = (0.3 * np_mod.sin(2 * np_mod.pi * freq * t)).astype(np_mod.float32)

    out_idx = _find_device(sd, "CABLE Input", "output")
    in_idx = _find_device(sd, "CABLE Output", "input")
    if out_idx is None or in_idx is None:
        print("  Cannot run tone test — CABLE not found.")
        return False

    # Start recording before play, capture for slightly longer than play to catch tail.
    rec = sd.rec(
        int(sample_rate * (duration + 0.5)),
        samplerate=sample_rate,
        channels=1,
        device=in_idx,
        dtype="float32",
    )
    time.sleep(0.05)  # let recorder warm up
    sd.play(tone, samplerate=sample_rate, device=out_idx, blocking=True)
    sd.wait()  # wait for record buffer to finish

    # Analyse: peak amplitude in captured signal should be > 0.05.
    captured = rec.flatten()
    peak = float(np_mod.abs(captured).max()) if captured.size else 0.0
    print(f"  Captured peak amplitude: {peak:.4f}  (expected > 0.05)")
    if peak < 0.05:
        print("  [FAIL] Tone did not reach the capture side. Check cable routing or sample rate.")
        return False
    print("  [OK] Tone end-to-end loopback verified.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify VB-CABLE A+B install for autonomous testing.")
    parser.add_argument("--tone-test", action="store_true", help="Play+capture a tone to verify routing.")
    args = parser.parse_args()

    audio = _try_import_audio()
    if audio is None:
        print("Install sounddevice + numpy: py -3.11 -m pip install sounddevice numpy")
        return 2
    sd, np_mod = audio

    ok_presence = verify_presence(sd)
    if not ok_presence:
        _print_install_help()
        return 1

    if args.tone_test:
        ok_tone = tone_test(sd, np_mod)
        if not ok_tone:
            return 1

    print("VB-CABLE A+B verified. Ready for the doctor harness driver.")
    print("Next: ensure Ava is running (start_ava.bat), then:")
    print("  py -3.11 scripts/diagnostic_session.py --probe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
