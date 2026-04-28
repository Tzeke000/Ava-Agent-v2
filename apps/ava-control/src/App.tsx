import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, ApiLogEntry, getJson, getText, postJson, registerApiLogger } from "./api";
import { JsonBlock, Kv, Section } from "./components/Ui";

/** Operator HTTP API aggregate (brain/operator_server.py — started from avaagent.py). */
type Snapshot = Record<string, unknown>;
type ChatMessage = { role?: string; content?: string };

const TABS = [
  { id: "chat" as const, label: "Chat" },
  { id: "status" as const, label: "Status" },
  { id: "memory" as const, label: "Memory" },
  { id: "models" as const, label: "Models / Brains" },
  { id: "workbench" as const, label: "Workbench" },
  { id: "identity" as const, label: "Identity" },
  { id: "debug" as const, label: "Debug" },
];
type TabId = (typeof TABS)[number]["id"];

function asRecord(v: unknown): Record<string, unknown> | undefined {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : undefined;
}

export default function App() {
  const [tab, setTab] = useState<TabId>("chat");
  const [online, setOnline] = useState(false);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [pollErr, setPollErr] = useState<string>("");
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);

  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatHist, setChatHist] = useState<ChatMessage[]>([]);
  const [lastChatErr, setLastChatErr] = useState<string>("");
  const [wbActionMsg, setWbActionMsg] = useState<string>("");
  const [chatThinking, setChatThinking] = useState(false);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const [cameraTick, setCameraTick] = useState(() => Date.now());
  const [cameraFrameOk, setCameraFrameOk] = useState(false);

  const [overrideModel, setOverrideModel] = useState("");
  const [overrideMode, setOverrideMode] = useState("");
  const [routeMsg, setRouteMsg] = useState<string>("");

  const [identity, setIdentity] = useState<{ identity: string; soul: string; user: string; err?: string }>({
    identity: "",
    soul: "",
    user: "",
  });

  const [apiCallLog, setApiCallLog] = useState<ApiLogEntry[]>([]);
  const [lastChatResponse, setLastChatResponse] = useState<Record<string, unknown> | null>(null);
  const [lastSnapshotRaw, setLastSnapshotRaw] = useState<Snapshot | null>(null);
  const [debugExportText, setDebugExportText] = useState<string>("");
  const [debugExportBusy, setDebugExportBusy] = useState(false);
  const [appEventLog, setAppEventLog] = useState<{ ts: string; message: string }[]>([]);
  const [shutdownConfirmOpen, setShutdownConfirmOpen] = useState(false);
  const [shutdownInProgress, setShutdownInProgress] = useState(false);
  const [shutdownGoodbye, setShutdownGoodbye] = useState("");
  const [shutdownDone, setShutdownDone] = useState(false);
  const [shutdownError, setShutdownError] = useState<string>("");
  const prevOnlineRef = useRef<boolean | null>(null);

  const pushEvent = useCallback((message: string) => {
    const row = { ts: new Date().toISOString(), message };
    setAppEventLog((prev) => [row, ...prev].slice(0, 400));
  }, []);

  useEffect(() => {
    registerApiLogger((entry) => {
      setApiCallLog((prev) => [entry, ...prev].slice(0, 50));
    });
    return () => registerApiLogger(null);
  }, []);

  const refreshSnapshotOnly = useCallback(async () => {
    setPollErr("");
    try {
      await getJson<{ ok?: boolean }>("/api/v1/health");
      const s = await getJson<Snapshot>("/api/v1/snapshot");
      setSnap(s);
      setLastSnapshotRaw(s);
      setOnline(true);
      setLastUpdated(typeof s.ts === "number" ? s.ts * 1000 : Date.now());
    } catch (e) {
      setOnline(false);
      setSnap(null);
      setLastSnapshotRaw(null);
      setPollErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const pollChatHistory = useCallback(async (): Promise<ChatMessage[] | null> => {
    try {
      const histRes = await getJson<{ ok?: boolean; messages?: ChatMessage[] }>("/api/v1/chat/history");
      if (Array.isArray(histRes.messages)) {
        setChatHist(histRes.messages);
        return histRes.messages;
      }
    } catch {
      /* optional */
    }
    return null;
  }, []);

  const poll = useCallback(async () => {
    await refreshSnapshotOnly();
    await pollChatHistory();
  }, [refreshSnapshotOnly, pollChatHistory]);

  useEffect(() => {
    if (prevOnlineRef.current === null) {
      prevOnlineRef.current = online;
      return;
    }
    if (prevOnlineRef.current !== online) {
      pushEvent(`Backend ${online ? "online" : "offline"}`);
      prevOnlineRef.current = online;
    }
  }, [online, pushEvent]);

  useEffect(() => {
    void poll();
    const id = window.setInterval(() => void poll(), 5000);
    return () => window.clearInterval(id);
  }, [poll]);

  useEffect(() => {
    if (tab !== "identity") return;
    let cancelled = false;
    (async () => {
      try {
        const [identityMd, soul, user] = await Promise.all([
          getText("/api/v1/identity/IDENTITY").catch(() => ""),
          getText("/api/v1/identity/SOUL").catch(() => ""),
          getText("/api/v1/identity/USER").catch(() => ""),
        ]);
        if (!cancelled) setIdentity({ identity: identityMd, soul, user });
      } catch (e) {
        if (!cancelled)
          setIdentity((x) => ({
            ...x,
            err: e instanceof Error ? e.message : String(e),
          }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab]);

  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [chatHist, chatThinking]);

  useEffect(() => {
    const id = window.setInterval(() => {
      setCameraTick(Date.now());
    }, 2000);
    return () => window.clearInterval(id);
  }, []);

  const ribbon = asRecord(snap?.ribbon);
  const hb = asRecord(snap?.heartbeat_runtime);
  const models = asRecord(snap?.models);
  const memory = asRecord(snap?.memory_continuity);
  const wb = asRecord(snap?.workbench);
  const tts = asRecord(snap?.tts);

  const sendChat = async () => {
    const t = chatInput.trim();
    if (!t) return;
    setChatBusy(true);
    setChatThinking(true);
    setLastChatErr("");
    pushEvent(`Chat: sending user message (${t.length} chars)`);
    setChatHist((prev) => [...prev, { role: "user", content: t }]);
    setChatInput("");
    try {
      const response = await postJson<Record<string, unknown>>("/api/v1/chat", { message: t });
      setLastChatResponse({
        ...response,
        debug_reply_source:
          typeof response.debug_reply_source === "string" ? response.debug_reply_source : "empty",
      });

      const reply =
        (typeof response.reply === "string" && response.reply.trim()) ||
        (typeof response.assistant_reply === "string" && response.assistant_reply.trim()) ||
        (typeof response.message === "string" && response.message.trim()) ||
        (typeof response.text === "string" && response.text.trim()) ||
        "";

      if (reply) {
        setChatHist((prev) => [...prev, { role: "assistant", content: reply }]);
        pushEvent(`Chat: received reply (${reply.length} chars)`);
        void refreshSnapshotOnly();
        return;
      }

      // 2) Empty / missing reply — sync from canonical history (Gradio path may have updated it)
      pushEvent("Chat: empty reply field — refreshing /api/v1/chat/history");
      const msgs = await pollChatHistory();

      let recovered = false;
      if (msgs && msgs.length > 0) {
        let userIdx = -1;
        for (let i = msgs.length - 1; i >= 0; i--) {
          const m = msgs[i];
          if (m.role === "user" && String(m.content ?? "").trim() === t) {
            userIdx = i;
            break;
          }
        }
        const next = userIdx >= 0 ? msgs[userIdx + 1] : undefined;
        if (next?.role === "assistant" && String(next.content ?? "").trim()) {
          recovered = true;
        }
      }

      if (!recovered) {
        const errMsg =
          "No reply from Ava: the \"reply\" field was empty and chat history did not show an assistant message after your text.";
        setLastChatErr(errMsg);
        setChatHist((prev) => [
          ...prev,
          {
            role: "system",
            content:
              "No reply received (empty \"reply\" from server and nothing in history yet). Open the Debug tab or try again.",
          },
          {
            role: "system",
            content: `Raw /api/v1/chat response:\n${JSON.stringify(response, null, 2)}`,
          },
        ]);
        pushEvent("Chat: no reply after POST and history poll");
      } else {
        setLastChatErr("");
        pushEvent("Chat: recovered assistant turn from history");
      }

      void refreshSnapshotOnly();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      pushEvent(`Chat send error: ${msg}`);
      if (msg.includes("404")) {
        setLastChatErr("Chat endpoint not yet wired. Expected path: /api/v1/chat");
      } else {
        setLastChatErr(msg);
      }
    } finally {
      setChatBusy(false);
      setChatThinking(false);
    }
  };

  const applyModelOverride = async () => {
    setRouteMsg("");
    try {
      const r = await postJson<Record<string, unknown>>("/api/v1/routing/override", {
        model: overrideModel.trim() || null,
        cognitive_mode: overrideMode.trim() || null,
      });
      setRouteMsg(`Override applied: ${JSON.stringify(r)}`);
      pushEvent(`Model routing override applied (${JSON.stringify(r)})`);
      setOverrideModel("");
      setOverrideMode("");
      await poll();
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      pushEvent(`Model override failed: ${m}`);
      setRouteMsg(m);
    }
  };

  const displayMessages = useMemo(() => chatHist.slice(-200), [chatHist]);

  const memThreads = memory?.active_threads;
  const threadList = Array.isArray(memThreads) ? memThreads : [];
  const memoryCount = threadList.length;

  const availModels = models?.available_models;
  const modelTags = Array.isArray(availModels) ? (availModels as string[]) : [];
  const wbMeta = asRecord(wb?.workbench_meta);
  const wbProposals = Array.isArray(wbMeta?.proposals) ? (wbMeta?.proposals as Record<string, unknown>[]) : [];
  const selectedProposalId = wbProposals.length ? String(wbProposals[0].proposal_id ?? "") : "";
  const vision = asRecord(snap?.vision);
  const perception = asRecord(vision?.perception);
  const personIdentity =
    String(perception?.resolved_face_identity ?? "").trim() ||
    String(perception?.stable_face_identity ?? "").trim() ||
    String(perception?.recognized_text ?? "").trim() ||
    "Unknown";
  const personConfidenceRaw = Number(perception?.interpretation_confidence ?? 0);
  const personConfidencePct = Number.isFinite(personConfidenceRaw)
    ? Math.max(0, Math.min(100, Math.round(personConfidenceRaw * 100)))
    : 0;
  const sceneSummary = String(perception?.scene_compact_summary ?? "").trim() || "No scene summary yet.";
  const moodLine =
    String(perception?.face_status ?? "").trim() || String(ribbon?.nuance_tone ?? "").trim() || "Neutral / steady";

  const updatedLabel = lastUpdated ? new Date(lastUpdated).toLocaleString() : "—";
  const frameUrl = `${API_BASE}/api/v1/vision/latest_frame?t=${cameraTick}`;

  const toggleTts = async () => {
    try {
      const res = await postJson<Record<string, unknown>>("/api/v1/tts/toggle", {});
      pushEvent(`TTS toggle -> enabled=${String(res.enabled ?? false)} engine=${String(res.engine ?? "none")}`);
      await poll();
    } catch (e) {
      pushEvent(`TTS toggle failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const runShutdown = async () => {
    setShutdownConfirmOpen(false);
    setShutdownInProgress(true);
    setShutdownError("");
    setShutdownGoodbye("");
    try {
      const res = await postJson<Record<string, unknown>>("/api/v1/shutdown", {});
      const goodbye = String(res.goodbye ?? "Goodnight, Zeke.");
      setShutdownGoodbye(goodbye);
      pushEvent(`Shutdown endpoint returned note_saved=${String(res.note_saved ?? false)}`);
      window.setTimeout(() => {
        setShutdownDone(true);
        try {
          window.close();
        } catch {
          // Browser fallback.
        }
      }, 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setShutdownError(msg);
      setShutdownInProgress(false);
      pushEvent(`Shutdown failed: ${msg}`);
    }
  };

  const workbenchAction = async (action: "approve" | "reject", proposalId?: string) => {
    setWbActionMsg("");
    try {
      const path = action === "approve" ? "/api/v1/workbench/approve" : "/api/v1/workbench/reject";
      const payload = { proposal_id: proposalId || selectedProposalId || null };
      pushEvent(`Workbench: ${action} proposal ${payload.proposal_id ?? "(none)"}`);
      const res = await postJson<Record<string, unknown>>(path, payload);
      setWbActionMsg(String(res.message ?? `${action} request sent`));
      await poll();
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      pushEvent(`Workbench ${action} error: ${m}`);
      setWbActionMsg(m);
    }
  };

  const fetchDebugExport = async () => {
    setDebugExportBusy(true);
    try {
      const text = await getText("/api/v1/debug/export");
      setDebugExportText(text);
      pushEvent("Fetched GET /api/v1/debug/export");
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      setDebugExportText(`(error) ${m}`);
      pushEvent(`Debug export failed: ${m}`);
    } finally {
      setDebugExportBusy(false);
    }
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      pushEvent(`Copied ${label} to clipboard`);
    } catch (e) {
      pushEvent(`Clipboard error (${label}): ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const lastReplyPresent =
    lastChatResponse &&
    (
      (typeof lastChatResponse.reply === "string" && lastChatResponse.reply.trim() !== "") ||
      (typeof lastChatResponse.assistant_reply === "string" &&
        lastChatResponse.assistant_reply.trim() !== "") ||
      (typeof lastChatResponse.message === "string" && lastChatResponse.message.trim() !== "") ||
      (typeof lastChatResponse.text === "string" && lastChatResponse.text.trim() !== "")
    );

  const lastReplyEmpty = lastChatResponse !== null && !lastReplyPresent;

  return (
    <div className="app operator-app">
      <header className="op-header">
        <div className="op-brand">
          <span className="op-title">Ava</span>
          <span className={`op-pill ${online ? "on" : "off"}`}>{online ? "Live" : "Offline"}</span>
        </div>
        <div className="op-meta">
          <span className="op-meta-item">Brain {String(models?.selected_model ?? "—")}</span>
          <span className="op-meta-item">Heartbeat {String(hb?.heartbeat_mode ?? "—")}</span>
          <span className="op-meta-item op-meta-issue">Issue {String(hb?.runtime_active_issue_summary ?? "none")}</span>
          <span className="op-meta-item">Updated {updatedLabel}</span>
          <button
            type="button"
            className="btn ghost op-header-btn"
            onClick={() => void toggleTts()}
            disabled={shutdownInProgress}
            title={`TTS engine: ${String(tts?.engine ?? "none")}`}
          >
            TTS {Boolean(tts?.enabled) ? "On" : "Off"} ({String(tts?.engine ?? "none")})
          </button>
          <button
            type="button"
            className="btn op-shutdown-btn"
            onClick={() => setShutdownConfirmOpen(true)}
            disabled={shutdownInProgress}
          >
            Shut Down
          </button>
        </div>
      </header>

      {!online && (
        <div className="op-banner">
          Backend not responding on :5876. Start <code>avaagent.py</code> (operator HTTP must be enabled).{" "}
          {pollErr ? `(${pollErr})` : ""}
        </div>
      )}

      <div className={`op-body ${shutdownInProgress ? "shutdown-locked" : ""}`}>
        <nav className="op-nav" aria-label="Primary">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={tab === t.id ? "active" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <main className="op-main">
          {tab === "chat" && (
            <div className="op-pane op-pane-chat">
              <div className="chat-two-panel">
                <aside className="chat-camera-panel">
                  <h2 className="op-h1">Camera</h2>
                  <div className="camera-frame-shell">
                    {cameraFrameOk ? null : (
                      <div className="camera-placeholder">No camera feed</div>
                    )}
                    <img
                      className="camera-frame"
                      src={frameUrl}
                      alt="Ava camera feed"
                      onLoad={() => setCameraFrameOk(true)}
                      onError={() => setCameraFrameOk(false)}
                      style={{ display: cameraFrameOk ? "block" : "none" }}
                    />
                  </div>
                  <Section title="Awareness">
                    <Kv
                      items={[
                        { label: "Seen person", value: personIdentity },
                        { label: "Confidence", value: `${personConfidencePct}%` },
                        { label: "Scene", value: sceneSummary },
                        { label: "Emotion / mood", value: moodLine },
                      ]}
                    />
                  </Section>
                </aside>
                <section className="chat-main-panel">
                  <h1 className="op-h1">Chat</h1>
                  <p className="op-lead">
                    Uses <code>POST /api/v1/chat</code> and <code>GET /api/v1/chat/history</code>.
                  </p>
                  <div className="chat-scroll chat-scroll-full" ref={chatScrollRef}>
                    {displayMessages.length === 0 && (
                      <p className="op-muted">No messages yet. Send text below — history syncs from the canonical log.</p>
                    )}
                    {displayMessages.map((m, i) => {
                      const rk =
                        m.role === "assistant"
                          ? "assistant"
                          : m.role === "system"
                            ? "system"
                            : "user";
                      return (
                        <div key={i} className={`chat-bubble chat-${rk}`}>
                          <span className="chat-role">{m.role ?? "?"}</span>
                          <div className="chat-text">{String(m.content ?? "")}</div>
                        </div>
                      );
                    })}
                    {chatThinking && (
                      <div className="typing-line">
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                        <span className="typing-dot" />
                        <span className="typing-text">Ava is thinking...</span>
                      </div>
                    )}
                  </div>
                  <div className="chat-compose chat-compose-stick">
                    <textarea
                      rows={3}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Message Ava…"
                      disabled={chatBusy}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void sendChat();
                        }
                      }}
                    />
                    <div className="chat-actions">
                      <button type="button" className="btn primary" disabled={chatBusy || !online} onClick={() => void sendChat()}>
                        {chatBusy ? "Sending…" : "Send"}
                      </button>
                      <button type="button" className="btn ghost" disabled title="Voice capture not wired in operator API yet">
                        Voice — coming soon
                      </button>
                    </div>
                  </div>
                  {lastChatErr ? <p className="op-error">{lastChatErr}</p> : null}
                </section>
              </div>
            </div>
          )}

          {tab === "status" && (
            <div className="op-pane">
              <h1 className="op-h1">Status</h1>
              <p className="op-lead">Polled every 5s via <code>GET /api/v1/snapshot</code> (no separate <code>/status</code> route).</p>
              {!online ? (
                <p className="op-banner-inline">Offline — snapshot unavailable.</p>
              ) : (
                <Section title="Runtime">
                  <Kv
                    items={[
                      { label: "Heartbeat mode", value: hb?.heartbeat_mode },
                      { label: "Brain / model", value: models?.selected_model },
                      { label: "Cognitive mode", value: models?.cognitive_mode },
                      { label: "Runtime readiness", value: hb?.runtime_ready_state },
                      { label: "Active issue", value: hb?.runtime_active_issue_summary },
                      { label: "Camera / vision", value: ribbon?.vision_status },
                      { label: "Snapshot ts", value: snap?.ts },
                    ]}
                  />
                </Section>
              )}
            </div>
          )}

          {tab === "memory" && (
            <div className="op-pane">
              <h1 className="op-h1">Memory</h1>
              <p className="op-lead">
                From snapshot <code>memory_continuity</code>. There is no dedicated memory list API yet.
              </p>
              {!online ? (
                <p className="op-muted">Not connected.</p>
              ) : (
                <>
                  <Section title="Summary">
                    <Kv
                      items={[
                        { label: "Strategic continuity", value: memory?.strategic_continuity_summary },
                        { label: "Relationship carryover", value: memory?.relationship_carryover },
                        { label: "Thread-like entries (count)", value: memoryCount },
                        { label: "Unfinished thread?", value: memory?.unfinished_thread_present },
                      ]}
                    />
                  </Section>
                  <Section title="Active threads (snapshot)">
                    {threadList.length === 0 ? (
                      <p className="op-muted">No structured threads in snapshot.</p>
                    ) : (
                      <JsonBlock data={threadList} />
                    )}
                  </Section>
                </>
              )}
            </div>
          )}

          {tab === "models" && (
            <div className="op-pane">
              <h1 className="op-h1">Models / Brains</h1>
              <p className="op-lead">
                Discovery + routing from snapshot; switch uses <code>POST /api/v1/routing/override</code>.
              </p>
              {!online ? (
                <p className="op-muted">Not connected.</p>
              ) : (
                <>
                  <Section title="Current routing">
                    <Kv
                      items={[
                        { label: "Selected model", value: models?.selected_model },
                        { label: "Fallback", value: models?.fallback_model },
                        { label: "Reason", value: models?.routing_reason },
                        { label: "Override (host)", value: models?.override_model },
                      ]}
                    />
                  </Section>
                  <Section title="Switch model">
                    <label className="op-label">Model tag</label>
                    <input
                      className="op-input"
                      value={overrideModel}
                      onChange={(e) => setOverrideModel(e.target.value)}
                      placeholder="e.g. llama3:latest"
                      list="model-tags"
                    />
                    <datalist id="model-tags">
                      {modelTags.map((m) => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                    <label className="op-label">Cognitive mode (optional)</label>
                    <input
                      className="op-input"
                      value={overrideMode}
                      onChange={(e) => setOverrideMode(e.target.value)}
                      placeholder="Clear override: leave blank and apply"
                    />
                    <button type="button" className="btn primary" onClick={() => void applyModelOverride()}>
                      Apply override
                    </button>
                    {routeMsg ? <p className="op-note">{routeMsg}</p> : null}
                  </Section>
                  <Section title="Available tags (snapshot)">
                    <p className="op-muted">{modelTags.length ? modelTags.join(", ") : "None listed"}</p>
                  </Section>
                </>
              )}
            </div>
          )}

          {tab === "workbench" && (
            <div className="op-pane">
              <h1 className="op-h1">Workbench</h1>
              <p className="op-lead">
                Snapshot fields + index text; approve/reject now call operator HTTP and refresh state.
              </p>
              {!online ? (
                <p className="op-muted">Not connected.</p>
              ) : (
                <>
                  <Section title="State">
                    <Kv
                      items={[
                        { label: "Has proposal", value: wb?.workbench_has_proposal },
                        { label: "Top title", value: wb?.workbench_top_proposal_title },
                        { label: "Summary", value: wb?.workbench_summary },
                        { label: "Execution ready", value: wb?.workbench_execution_ready },
                      ]}
                    />
                  </Section>
                  {typeof wb?.workbench_index_text === "string" && wb.workbench_index_text.trim() ? (
                    <Section title="Index preview">
                      <pre className="mono-block">{wb.workbench_index_text.slice(0, 12000)}</pre>
                    </Section>
                  ) : (
                    <p className="op-muted">No workbench index text on snapshot.</p>
                  )}
                  <Section title="Actions">
                    <div className="row-gap">
                      <button
                        type="button"
                        className="btn"
                        onClick={() => void workbenchAction("approve", selectedProposalId)}
                        disabled={!selectedProposalId}
                      >
                        Approve top proposal
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() => void workbenchAction("reject", selectedProposalId)}
                        disabled={!selectedProposalId}
                      >
                        Reject top proposal
                      </button>
                    </div>
                    {wbActionMsg ? <p className="op-note">{wbActionMsg}</p> : null}
                  </Section>
                  <Section title="workbench_meta">
                    <JsonBlock data={wb?.workbench_meta ?? {}} maxHeight={240} />
                  </Section>
                </>
              )}
            </div>
          )}

          {tab === "identity" && (
            <div className="op-pane">
              <h1 className="op-h1">Identity</h1>
              <p className="op-lead">
                Read-only via <code>GET /api/v1/identity/IDENTITY</code> (and SOUL, USER). No editing.
              </p>
              {identity.err ? <p className="op-error">{identity.err}</p> : null}
              {!online && !identity.identity && !identity.soul && !identity.user ? (
                <p className="op-muted">Offline — identity files not loaded.</p>
              ) : (
                <>
                  <Section title="IDENTITY.md">
                    <pre className="identity-ro">{identity.identity || "(empty or unavailable)"}</pre>
                  </Section>
                  <Section title="SOUL.md">
                    <pre className="identity-ro">{identity.soul || "(empty or unavailable)"}</pre>
                  </Section>
                  <Section title="USER.md">
                    <pre className="identity-ro">{identity.user || "(empty or unavailable)"}</pre>
                  </Section>
                </>
              )}
            </div>
          )}

          {tab === "debug" && (
            <div className="op-pane op-pane-debug">
              <h1 className="op-h1">Debug</h1>
              <p className="op-lead">
                Operator HTTP instrumentation. Paste <strong>Backend Debug Export</strong> for a full Ava handoff.
              </p>

              <Section title="1 — Live API response log">
                <div className="debug-toolbar">
                  <button type="button" className="btn ghost" onClick={() => setApiCallLog([])}>
                    Clear log
                  </button>
                  <span className="op-muted">{apiCallLog.length}/50 entries · newest first</span>
                </div>
                <div className="debug-log-scroll">
                  {apiCallLog.length === 0 ? (
                    <p className="op-muted">No API calls recorded yet.</p>
                  ) : (
                    apiCallLog.map((e, idx) => (
                      <div key={`${e.timestamp}-${e.endpoint}-${idx}`} className="debug-api-entry">
                        <div className="debug-api-meta">
                          <span className="debug-ts">{e.timestamp}</span>
                          <span className={`debug-status ${e.status >= 400 ? "bad" : ""}`}>{e.status}</span>
                          <span className="debug-endpoint">{e.endpoint}</span>
                        </div>
                        <pre className="debug-pre">{e.responseBody}</pre>
                      </div>
                    ))
                  )}
                </div>
              </Section>

              <Section title="2 — Last chat response (POST /api/v1/chat)">
                {lastChatResponse === null ? (
                  <p className="op-muted">No chat POST completed in this session yet.</p>
                ) : (
                  <>
                    <p className="debug-reply-flag">
                      reply field:{" "}
                      <strong className={lastReplyPresent ? "debug-ok" : "debug-bad"}>
                        {lastReplyPresent ? "present (non-empty)" : "missing or empty"}
                      </strong>
                    </p>
                    <p className="debug-reply-flag">
                      debug_reply_source:{" "}
                      <strong>
                        {typeof lastChatResponse.debug_reply_source === "string"
                          ? lastChatResponse.debug_reply_source
                          : "empty"}
                      </strong>
                    </p>
                    {lastReplyEmpty ? (
                      <p className="debug-fat-warn">
                        Reply text was empty after checking reply → assistant_reply → message → text. Inspect JSON below.
                      </p>
                    ) : null}
                    <pre className="debug-pre">{JSON.stringify(lastChatResponse, null, 2)}</pre>
                  </>
                )}
              </Section>

              <Section title="3 — Backend debug export">
                <div className="debug-toolbar">
                  <button type="button" className="btn primary" disabled={debugExportBusy} onClick={() => void fetchDebugExport()}>
                    {debugExportBusy ? "Fetching…" : "Fetch debug export"}
                  </button>
                  <button
                    type="button"
                    className="btn ghost"
                    disabled={!debugExportText}
                    onClick={() => void copyToClipboard(debugExportText, "debug export")}
                  >
                    Copy to clipboard
                  </button>
                </div>
                <p className="op-muted">
                  GET <code>/api/v1/debug/export</code> — plain-text bundle from{" "}
                  <code>build_debug_export(host)</code>.
                </p>
                <pre className="debug-pre tall">{debugExportText || "(not fetched)"}</pre>
              </Section>

              <Section title="4 — Snapshot raw (last poll)">
                <button
                  type="button"
                  className="btn ghost"
                  disabled={!lastSnapshotRaw}
                  onClick={() =>
                    lastSnapshotRaw && void copyToClipboard(JSON.stringify(lastSnapshotRaw, null, 2), "snapshot JSON")
                  }
                >
                  Copy to clipboard
                </button>
                <pre className="debug-pre tall">
                  {lastSnapshotRaw ? JSON.stringify(lastSnapshotRaw, null, 2) : "(no snapshot yet)"}
                </pre>
              </Section>

              <Section title="5 — App event log">
                <button
                  type="button"
                  className="btn ghost"
                  disabled={appEventLog.length === 0}
                  onClick={() =>
                    void copyToClipboard(
                      appEventLog.map((r) => `[${r.ts}] ${r.message}`).join("\n"),
                      "event log"
                    )
                  }
                >
                  Copy to clipboard
                </button>
                <pre className="debug-pre tall">
                  {appEventLog.length === 0
                    ? "(no events)"
                    : appEventLog.map((r) => `[${r.ts}] ${r.message}`).join("\n")}
                </pre>
              </Section>
            </div>
          )}
        </main>
      </div>
      {shutdownConfirmOpen && (
        <div className="shutdown-modal-backdrop">
          <div className="shutdown-modal">
            <h2>Shut down Ava?</h2>
            <p>She will save her thoughts before closing.</p>
            <div className="shutdown-modal-actions">
              <button type="button" className="btn op-shutdown-btn" onClick={() => void runShutdown()}>
                Shut Down
              </button>
              <button type="button" className="btn ghost" onClick={() => setShutdownConfirmOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
      {shutdownInProgress && (
        <div className="shutdown-overlay">
          <div className="shutdown-overlay-card">
            <h2>{shutdownGoodbye ? "Goodnight from Ava" : "Ava is saving her thoughts..."}</h2>
            {shutdownGoodbye ? <p className="shutdown-goodbye-text">{shutdownGoodbye}</p> : <p>Please wait.</p>}
            {shutdownDone ? <p className="shutdown-goodbye-done">Ava has shut down.</p> : null}
            {shutdownError ? <p className="op-error">{shutdownError}</p> : null}
          </div>
        </div>
      )}
    </div>
  );
}
