/**
 * Phase 48 — Desktop Widget Orb
 *
 * Minimal always-on-top floating orb window. Polls operator HTTP for
 * mood state and renders OrbCanvas in a transparent 150×150 frame.
 * Position is persisted via the operator API.
 *
 * Bootstrap: Ava tracks where the widget gets moved and starts defaulting there.
 */
import { useEffect, useRef, useState } from "react";
import OrbCanvas from "./components/OrbCanvas";
import { API_BASE, getJson } from "./api";

const EMOTION_COLOR: Record<string, string> = {
  calmness: "#1a6cf5", joy: "#f5c518", happiness: "#f5c518", excitement: "#ff6b00",
  curiosity: "#00d4d4", interest: "#00d4d4", boredom: "#4a5568", frustration: "#e53e3e",
  sadness: "#553c9a", anger: "#c53030", fear: "#44337a", anxiety: "#44337a",
  surprise: "#d53f8c", trust: "#38a169", love: "#ed64a6", pride: "#6b46c1",
  confidence: "#ecc94b", awe: "#4299e1", confusion: "#9f7aea", loneliness: "#2c5282",
  contentment: "#68d391", relief: "#81e6d9", nostalgia: "#d4a574", hope: "#f6e05e",
  contempt: "#4a5568", shame: "#b7791f", guilt: "#2d3748", anticipation: "#d69e2e",
};

type OrbState = "idle" | "thinking" | "deep" | "speaking" | "bored" | "excited" | "offline";

function getState(snap: Record<string, unknown> | null, online: boolean): OrbState {
  if (!online || !snap) return "offline";
  const rb = snap.ribbon as Record<string, unknown> | undefined;
  const hbMode = String(rb?.heartbeat_mode || "").toLowerCase();
  if (hbMode.includes("conversation")) return "speaking";
  if (hbMode.includes("maintenance") || hbMode.includes("learning")) return "thinking";
  if (hbMode.includes("idle")) return "idle";
  return "idle";
}

function getEmotion(snap: Record<string, unknown> | null): [string, string] {
  if (!snap) return ["calmness", "#1a6cf5"];
  try {
    const p = snap.perception as Record<string, unknown> | undefined;
    const emo = String(p?.emotion_label || (snap as any)?.emotion_label || "calmness").toLowerCase();
    return [emo, EMOTION_COLOR[emo] || "#1a6cf5"];
  } catch {
    return ["calmness", "#1a6cf5"];
  }
}

// Save widget drag position back to the state file via operator API
function savePosition(x: number, y: number): void {
  fetch(`${API_BASE}/api/v1/widget/position`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x, y }),
  }).catch(() => {});
}

export default function WidgetApp() {
  const [online, setOnline] = useState(false);
  const [snap, setSnap] = useState<Record<string, unknown> | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; winX: number; winY: number } | null>(null);

  // Poll snapshot
  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const data = await getJson("/api/v1/snapshot");
        if (alive && data && typeof data === "object") {
          setSnap(data as Record<string, unknown>);
          setOnline(true);
        }
      } catch {
        if (alive) setOnline(false);
      }
    };
    poll();
    const iv = setInterval(poll, 3000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  // Load saved position on mount and apply to window
  useEffect(() => {
    getJson("/api/v1/widget/position")
      .then((pos) => {
        if (pos && typeof pos === "object") {
          const p = pos as Record<string, unknown>;
          const x = Number(p.x) || 100;
          const y = Number(p.y) || 100;
          // Attempt to move the Tauri window to saved position (best-effort)
          try {
            (window as any).__TAURI_INTERNALS__?.invoke("plugin:window|set_position", {
              label: "widget",
              position: { Physical: { x, y } },
            }).catch(() => {});
          } catch { /* ok */ }
        }
      })
      .catch(() => {});
  }, []);

  const [emotion, emotionColor] = getEmotion(snap);
  const orbState = getState(snap, online);

  // Phase 49: pointer morph when Ava is pointing at something
  const widgetBlock = snap?.widget as Record<string, unknown> | undefined;
  const isPointing = Boolean(widgetBlock?.pointing);
  const shapeOverride = isPointing ? "pointer" : undefined;

  return (
    <div
      data-tauri-drag-region
      style={{
        width: "150px",
        height: "150px",
        background: "transparent",
        overflow: "hidden",
        cursor: "grab",
        userSelect: "none",
      }}
    >
      <OrbCanvas
        emotion={emotion}
        emotionColor={emotionColor}
        state={orbState}
        size={150}
        shapeOverride={shapeOverride}
      />
    </div>
  );
}
