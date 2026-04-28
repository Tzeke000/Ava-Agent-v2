import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, getJson, getText, postJson } from "./api";
import { JsonBlock, Kv, Section } from "./components/Ui";

/** Operator HTTP API aggregate (brain/operator_server.py — started from avaagent.py). */
type Snapshot = Record<string, unknown>;

const TABS = [
  { id: "chat" as const, label: "Chat" },
  { id: "status" as const, label: "Status" },
  { id: "memory" as const, label: "Memory" },
  { id: "models" as const, label: "Models / Brains" },
  { id: "workbench" as const, label: "Workbench" },
  { id: "identity" as const, label: "Identity" },
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
  const [chatHist, setChatHist] = useState<{ role?: string; content?: string }[]>([]);
  const [lastChatErr, setLastChatErr] = useState<string>("");

  const [overrideModel, setOverrideModel] = useState("");
  const [overrideMode, setOverrideMode] = useState("");
  const [routeMsg, setRouteMsg] = useState<string>("");

  const [identity, setIdentity] = useState<{ identity: string; soul: string; user: string; err?: string }>({
    identity: "",
    soul: "",
    user: "",
  });

  const poll = useCallback(async () => {
    setPollErr("");
    try {
      const h = await fetch(`${API_BASE}/api/v1/health`, { method: "GET" });
      if (!h.ok) throw new Error(`${h.status}`);
      const s = await getJson<Snapshot>("/api/v1/snapshot");
      setSnap(s);
      setOnline(true);
      setLastUpdated(typeof s.ts === "number" ? s.ts * 1000 : Date.now());
    } catch (e) {
      setOnline(false);
      setSnap(null);
      setPollErr(e instanceof Error ? e.message : String(e));
    }
    try {
      const histRes = await getJson<{ ok?: boolean; messages?: { role?: string; content?: string }[] }>(
        "/api/v1/chat/history"
      );
      if (Array.isArray(histRes.messages)) setChatHist(histRes.messages);
    } catch {
      /* optional */
    }
  }, []);

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

  const ribbon = asRecord(snap?.ribbon);
  const hb = asRecord(snap?.heartbeat_runtime);
  const models = asRecord(snap?.models);
  const memory = asRecord(snap?.memory_continuity);
  const wb = asRecord(snap?.workbench);

  const sendChat = async () => {
    const t = chatInput.trim();
    if (!t) return;
    setChatBusy(true);
    setLastChatErr("");
    try {
      await postJson("/api/v1/chat", { message: t });
      setChatInput("");
      await poll();
    } catch (e) {
      setLastChatErr(e instanceof Error ? e.message : String(e));
    } finally {
      setChatBusy(false);
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
      setOverrideModel("");
      setOverrideMode("");
      await poll();
    } catch (e) {
      setRouteMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const displayMessages = useMemo(() => chatHist.slice(-200), [chatHist]);

  const memThreads = memory?.active_threads;
  const threadList = Array.isArray(memThreads) ? memThreads : [];
  const memoryCount = threadList.length;

  const availModels = models?.available_models;
  const modelTags = Array.isArray(availModels) ? (availModels as string[]) : [];

  const updatedLabel = lastUpdated ? new Date(lastUpdated).toLocaleString() : "—";

  return (
    <div className="app operator-app">
      <header className="op-header">
        <div className="op-brand">
          <span className="op-title">Ava</span>
          <span className={`op-pill ${online ? "on" : "off"}`}>{online ? "Live" : "Offline"}</span>
        </div>
        <div className="op-meta">
          <span className="op-meta-item">API {API_BASE}</span>
          <span className="op-meta-item">Updated {updatedLabel}</span>
          {ribbon?.routing_selected_model != null && (
            <span className="op-meta-item">Brain {String(ribbon.routing_selected_model)}</span>
          )}
        </div>
      </header>

      {!online && (
        <div className="op-banner">
          Backend not responding on :5876. Start <code>avaagent.py</code> (operator HTTP must be enabled).{" "}
          {pollErr ? `(${pollErr})` : ""}
        </div>
      )}

      <div className="op-body">
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
            <div className="op-pane">
              <h1 className="op-h1">Chat</h1>
              <p className="op-lead">
                Uses <code>POST /api/v1/chat</code> and <code>GET /api/v1/chat/history</code>.
              </p>
              <div className="chat-scroll">
                {displayMessages.length === 0 && (
                  <p className="op-muted">No messages yet. Send text below — history syncs from the canonical log.</p>
                )}
                {displayMessages.map((m, i) => (
                  <div key={i} className={`chat-bubble chat-${m.role === "assistant" ? "assistant" : "user"}`}>
                    <span className="chat-role">{m.role ?? "?"}</span>
                    <div className="chat-text">{String(m.content ?? "")}</div>
                  </div>
                ))}
              </div>
              <div className="chat-compose">
                <textarea
                  rows={3}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Message Ava…"
                  disabled={chatBusy}
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
                Snapshot fields + index text when present. No <code>POST …/approve</code> routes on operator HTTP —
                buttons log only until backend exposes them.
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
                  <Section title="Actions (placeholder)">
                    <p className="op-muted">
                      Approve / Reject require new operator routes (e.g. tied to Gradio workbench handlers).
                    </p>
                    <div className="row-gap">
                      <button
                        type="button"
                        className="btn"
                        onClick={() =>
                          console.log("[workbench] approve (placeholder)", wb?.workbench_top_proposal_title ?? "")
                        }
                      >
                        Approve top proposal (log only)
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={() =>
                          console.log("[workbench] reject (placeholder)", wb?.workbench_top_proposal_title ?? "")
                        }
                      >
                        Reject top proposal (log only)
                      </button>
                    </div>
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
        </main>
      </div>
    </div>
  );
}
