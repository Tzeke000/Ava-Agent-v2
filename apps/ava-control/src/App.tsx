import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE, getJson, getText, postJson } from "./api";
import { ExpandPre, JsonBlock, Kv, Section } from "./components/Ui";

type Snap = Record<string, unknown>;

const TABS = [
  "chat",
  "heartbeat",
  "models",
  "vision",
  "memory",
  "workbench",
  "identity",
  "debug",
  "export",
] as const;
type Tab = (typeof TABS)[number];

const TAB_LABEL: Record<Tab, string> = {
  chat: "Chat",
  heartbeat: "Heartbeat",
  models: "Models",
  vision: "Vision",
  memory: "Memory",
  workbench: "Workbench",
  identity: "Self",
  debug: "Debug",
  export: "Debug export",
};

function asRecord(v: unknown): Record<string, unknown> | undefined {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : undefined;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [snap, setSnap] = useState<Snap | null>(null);
  const [err, setErr] = useState<string>("");
  const [ok, setOk] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [lastChat, setLastChat] = useState<Record<string, unknown> | null>(null);
  const [hist, setHist] = useState<{ role?: string; content?: string }[]>([]);
  const [exportText, setExportText] = useState("");
  const [overrideModel, setOverrideModel] = useState("");
  const [overrideMode, setOverrideMode] = useState("");
  const [identity, setIdentity] = useState<{ soul: string; identity: string; user: string }>({
    soul: "",
    identity: "",
    user: "",
  });

  const poll = useCallback(async () => {
    try {
      const s = await getJson<Snap>("/api/v1/snapshot");
      setSnap(s);
      setErr("");
      setOk(true);
    } catch (e) {
      setOk(false);
      setErr(e instanceof Error ? e.message : String(e));
    }
    try {
      const h = await getJson<{ ok?: boolean; messages?: { role?: string; content?: string }[] }>("/api/v1/chat/history");
      if (h.messages?.length) setHist(h.messages);
    } catch {
      /* history optional */
    }
  }, []);

  useEffect(() => {
    void poll();
    const id = setInterval(() => void poll(), 2800);
    return () => clearInterval(id);
  }, [poll]);

  const ribbon = asRecord(snap?.ribbon);
  const hb = asRecord(snap?.heartbeat_runtime);
  const models = asRecord(snap?.models);
  const vision = asRecord(snap?.vision);
  const perception = asRecord(vision?.perception);
  const memory = asRecord(snap?.memory_continuity);
  const wb = asRecord(snap?.workbench);
  const loop = asRecord(snap?.improvement_loop);
  const concerns = asRecord(snap?.concerns);
  const debugHuman = asRecord(snap?.debug);

  const ts = typeof snap?.ts === "number" ? snap.ts : Date.now();
  const frameUrl = `${API_BASE}/api/v1/vision/latest_frame?t=${Math.floor(ts * 1000)}`;

  const sendChat = async () => {
    const t = chatInput.trim();
    if (!t) return;
    setChatBusy(true);
    try {
      const r = await postJson<Record<string, unknown>>("/api/v1/chat", { message: t });
      setLastChat(r);
      setChatInput("");
      await poll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setChatBusy(false);
    }
  };

  const applyOverride = async () => {
    try {
      await postJson("/api/v1/routing/override", {
        model: overrideModel.trim() || null,
        cognitive_mode: overrideMode.trim() || null,
      });
      setOverrideModel("");
      setOverrideMode("");
      await poll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const loadExport = async () => {
    try {
      const t = await getText("/api/v1/debug/export");
      setExportText(t);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const loadIdentity = async () => {
    try {
      const [identityMd, soul, user] = await Promise.all([
        getText("/api/v1/identity/IDENTITY").catch(() => "(missing)"),
        getText("/api/v1/identity/SOUL").catch(() => "(missing)"),
        getText("/api/v1/identity/USER").catch(() => "(missing)"),
      ]);
      setIdentity({ identity: identityMd, soul, user });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (tab === "identity") void loadIdentity();
    if (tab === "export") void loadExport();
  }, [tab]);

  const historyPreview = useMemo(() => {
    if (hist.length) return hist.slice(-48);
    const h = lastChat?.canonical_history as { role?: string; content?: string }[] | undefined;
    return h?.length ? h.slice(-48) : [];
  }, [hist, lastChat]);

  const availModels = models?.available_models;
  const modelOptions = Array.isArray(availModels) ? (availModels as string[]) : [];

  const debugSummary = useMemo(() => {
    const r = ribbon || {};
    return [
      { label: "Heartbeat", value: String(r.heartbeat_mode ?? "") },
      { label: "Presence", value: String(r.presence_mode ?? "") },
      { label: "Brain / model", value: String(r.routing_selected_model ?? "") },
      { label: "Cognitive mode", value: String(r.cognitive_mode ?? "") },
      { label: "Vision", value: String(r.vision_status ?? "") },
      { label: "Voice", value: String(r.voice_turn_state ?? "") },
      { label: "Active issue", value: String(r.active_issue ?? "") },
      { label: "Workbench hint", value: String(r.workbench_hint ?? "") },
      { label: "Top concern", value: String(r.concerns_top ?? "") },
      { label: "Learning focus", value: String(hb?.learning_focus ?? "") },
      { label: "Improvement loop", value: String(loop?.improvement_loop_stage ?? "") },
    ];
  }, [ribbon, hb, loop]);

  return (
    <div className="app">
      <header className="ribbon-top">
        <div className="brand">
          <span className="brand-title">Ava</span>
          <span className={`conn ${ok ? "ok" : "bad"}`}>{ok ? "live" : "offline"}</span>
        </div>
        <div className="ribbon-chips" title={err || undefined}>
          <Chip k="Heartbeat" v={ribbon?.heartbeat_mode} />
          <Chip k="Brain" v={ribbon?.routing_selected_model} />
          <Chip k="Mode" v={ribbon?.cognitive_mode} />
          <Chip k="Vision" v={ribbon?.vision_status} />
          <Chip k="Voice" v={ribbon?.voice_turn_state} />
          <Chip k="Presence" v={ribbon?.presence_mode} />
          <Chip k="Issue" v={ribbon?.active_issue} narrow />
          <Chip k="Threads" v={ribbon?.threads_short} narrow />
          <Chip k="Workbench" v={ribbon?.workbench_hint} narrow />
          <Chip k="Ready" v={ribbon?.ready_state} />
          <Chip k="Override" v={ribbon?.routing_override || "none"} />
          <Chip k="Concern" v={ribbon?.concerns_top} narrow />
        </div>
      </header>

      <div className="body">
        <nav className="nav">
          {TABS.map((t) => (
            <button key={t} type="button" className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
              {TAB_LABEL[t]}
            </button>
          ))}
        </nav>

        <main className="main-pane">
          <p className="fineprint">
            Operator console · API <code>{API_BASE}</code>
            {ribbon?.gradio_url ? (
              <>
                {" "}
                · Gradio (optional) <code>{String(ribbon.gradio_url)}</code>
              </>
            ) : null}
            {err ? (
              <span className="err-inline">
                {" "}
                · {err}
              </span>
            ) : null}
          </p>

          {tab === "chat" && (
            <div className="tab-chat">
              <div className="chat-layout">
                <div className="chat-main">
                  <h2 className="h2">Chat</h2>
                  <div className="chat-msgs">
                    {historyPreview.map((m, i) => (
                      <div key={i} className={`msg msg-${m.role === "assistant" ? "assistant" : "user"}`}>
                        <div className="msg-role">{m.role}</div>
                        <div className="msg-body">{String(m.content ?? "")}</div>
                      </div>
                    ))}
                    {!historyPreview.length && (
                      <div className="muted">Send a message. History follows Ava’s canonical chat log (same source as Gradio).</div>
                    )}
                  </div>
                  <div className="row chat-input-row">
                    <textarea
                      rows={3}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Message Ava…"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                          e.preventDefault();
                          void sendChat();
                        }
                      }}
                    />
                    <button type="button" className="primary" disabled={chatBusy} onClick={() => void sendChat()}>
                      {chatBusy ? "…" : "Send"}
                    </button>
                  </div>
                  <p className="fineprint">
                    Tip: <kbd>Ctrl</kbd>+<kbd>Enter</kbd> to send. Voice capture still uses the Gradio UI mic path — open the fallback URL if
                    needed.
                  </p>
                  {lastChat && lastChat.ok === false && <JsonBlock data={lastChat} />}
                </div>

                <aside className="chat-sidebar">
                  <Section title="Live snapshot" muted="Updates with operator poll.">
                    <Kv
                      items={[
                        { label: "Brain", value: ribbon?.routing_selected_model as string },
                        { label: "Cognitive mode", value: ribbon?.cognitive_mode as string },
                        { label: "Tone / nuance", value: ribbon?.nuance_tone as string },
                        { label: "Heartbeat", value: ribbon?.heartbeat_mode as string },
                        { label: "Vision status", value: ribbon?.vision_status as string },
                        { label: "Voice", value: ribbon?.voice_turn_state as string },
                      ]}
                    />
                  </Section>
                  <Section title="Scene / camera" muted="Latest annotated frame when available.">
                    <div className="frame-wrap">
                      <img className="frame-img" src={frameUrl} alt="Latest annotated camera frame" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
                    </div>
                    <Kv
                      items={[
                        { label: "Scene", value: perception?.scene_compact_summary as string },
                        { label: "Trust", value: perception?.visual_truth_trusted as string },
                        { label: "Face", value: perception?.face_status as string },
                      ]}
                    />
                  </Section>
                  <Section title="Voice">
                    <p className="fineprint">
                      State: <b>{String(ribbon?.voice_turn_state ?? "—")}</b>
                    </p>
                    {typeof ribbon?.gradio_url === "string" && ribbon.gradio_url ? (
                      <a className="linkish" href={ribbon.gradio_url} target="_blank" rel="noreferrer">
                        Open Gradio for microphone / legacy controls
                      </a>
                    ) : null}
                  </Section>
                  {lastChat?.ok !== false && (
                    <Section title="Last turn" muted="After your last send.">
                      <Kv
                        items={[
                          { label: "Reply snippet", value: (lastChat?.reply as string)?.slice(0, 900) },
                          { label: "Face line", value: lastChat?.face_status as string },
                          {
                            label: "Route",
                            value: (lastChat?.visual as Record<string, string> | undefined)?.turn_route,
                          },
                        ]}
                      />
                    </Section>
                  )}
                </aside>
              </div>
            </div>
          )}

          {tab === "heartbeat" && (
            <>
              <h2 className="h2">Heartbeat / runtime</h2>
              <div className="two-col">
                <Section title="Heartbeat">
                  <Kv
                    items={[
                      { label: "Mode", value: hb?.heartbeat_mode as string },
                      { label: "Last tick reason", value: hb?.heartbeat_last_reason as string },
                      { label: "Summary", value: hb?.heartbeat_summary as string },
                      { label: "Tick id", value: hb?.heartbeat_tick_id as number },
                    ]}
                  />
                  <ExpandPre title="heartbeat_meta JSON" body={JSON.stringify(hb?.heartbeat_meta ?? {}, null, 2)} />
                </Section>
                <Section title="Presence & threads" muted="Quiet monitoring vs active conversation cues are reflected here descriptively.">
                  <Kv
                    items={[
                      { label: "Presence mode", value: hb?.runtime_presence_mode as string },
                      { label: "Operator summary", value: hb?.runtime_operator_summary as string },
                      { label: "Active issue", value: hb?.runtime_active_issue_summary as string },
                      { label: "Carryover threads", value: hb?.runtime_threads_summary as string },
                      { label: "Maintenance", value: hb?.runtime_maintenance_summary as string },
                      { label: "Ready state", value: hb?.runtime_ready_state as string },
                    ]}
                  />
                  <ExpandPre title="runtime_presence_meta" body={JSON.stringify(hb?.runtime_presence_meta ?? {}, null, 2)} />
                </Section>
              </div>
              <Section title="Adaptive learning">
                <Kv
                  items={[
                    { label: "Learning summary", value: hb?.learning_summary as string },
                    { label: "Learning focus", value: hb?.learning_focus as string },
                  ]}
                />
                <ExpandPre title="learning_meta" body={JSON.stringify(hb?.learning_meta ?? {}, null, 2)} />
              </Section>
              <Section title="Startup / carryover snapshot">
                <ExpandPre title="snapshot_carryover" body={JSON.stringify(hb?.snapshot_carryover ?? {}, null, 2)} />
              </Section>
            </>
          )}

          {tab === "models" && (
            <>
              <h2 className="h2">Models / brains</h2>
              <div className="two-col">
                <Section title="Current routing">
                  <Kv
                    items={[
                      { label: "Selected model", value: models?.selected_model as string },
                      { label: "Cognitive mode", value: models?.cognitive_mode as string },
                      { label: "Fallback model", value: models?.fallback_model as string },
                      { label: "Why this model", value: models?.routing_reason as string },
                      { label: "Confidence", value: models?.routing_confidence as number },
                      {
                        label: "Last switch hint",
                        value: (models?.switch_reason_last as string) || (models?.no_switch_reason_last as string),
                      },
                      { label: "Effective (host)", value: models?.host_last_effective_model as string },
                      { label: "Host cognitive", value: models?.host_last_cognitive_mode as string },
                    ]}
                  />
                  <ExpandPre title="routing_meta" body={JSON.stringify(models?.routing_meta ?? {}, null, 2)} />
                </Section>
                <Section
                  title="Operator override"
                  muted="Bounded override using the same globals as routing. Leave empty and apply to clear. Reversible anytime."
                >
                  <label className="lbl">Model tag</label>
                  <input
                    type="text"
                    value={overrideModel}
                    onChange={(e) => setOverrideModel(e.target.value)}
                    placeholder="e.g. llama3:latest"
                    list="model-pick"
                  />
                  <datalist id="model-pick">
                    {modelOptions.map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                  <label className="lbl">Cognitive mode (optional)</label>
                  <input
                    type="text"
                    value={overrideMode}
                    onChange={(e) => setOverrideMode(e.target.value)}
                    placeholder="e.g. social_chat_mode"
                  />
                  <div className="row" style={{ marginTop: "0.6rem" }}>
                    <button type="button" className="primary" onClick={() => void applyOverride()}>
                      Apply override
                    </button>
                  </div>
                  <Kv
                    items={[
                      { label: "Active override model", value: models?.override_model as string },
                      { label: "Active override mode", value: models?.override_mode as string },
                      { label: "Discovery source", value: models?.discovery_source as string },
                      { label: "Discovery error", value: models?.discovery_error as string },
                    ]}
                  />
                  <p className="fineprint">Available tags (from runtime discovery):</p>
                  <div className="chips">
                    {modelOptions.slice(0, 40).map((m) => (
                      <button key={m} type="button" className="chip-btn" onClick={() => setOverrideModel(m)}>
                        {m}
                      </button>
                    ))}
                    {modelOptions.length > 40 && <span className="muted">+{modelOptions.length - 40} more</span>}
                  </div>
                </Section>
              </div>
            </>
          )}

          {tab === "vision" && (
            <>
              <h2 className="h2">Vision / awareness</h2>
              <div className="two-col">
                <Section title="Frame">
                  <div className="frame-wrap wide">
                    <img className="frame-img" src={frameUrl} alt="Annotated frame" />
                  </div>
                </Section>
                <Section title="Perception summary">
                  <Kv
                    items={[
                      { label: "Vision status", value: perception?.vision_status as string },
                      { label: "Visual trust", value: String(perception?.visual_truth_trusted ?? "") },
                      { label: "Face", value: perception?.face_status as string },
                      { label: "Recognition", value: perception?.recognized_text as string },
                      { label: "Scene summary", value: perception?.scene_compact_summary as string },
                      { label: "Scene state", value: perception?.scene_overall_state as string },
                      { label: "Identity state", value: perception?.identity_state as string },
                      { label: "Resolved identity", value: perception?.resolved_face_identity as string },
                      { label: "Stable identity", value: perception?.stable_face_identity as string },
                      { label: "Quality", value: perception?.quality_label as string },
                      { label: "Blur", value: perception?.blur_label as string },
                      { label: "Freshness", value: perception?.acquisition_freshness as string },
                      { label: "Interpretation", value: perception?.interpretation_primary_event as string },
                      { label: "Confidence", value: perception?.interpretation_confidence as string },
                    ]}
                  />
                </Section>
              </div>
              <Section title="Concerns (vision-adjacent)" muted="Surfaced concerns that may intersect camera, trust, or scene interpretation.">
                <Kv
                  items={[
                    { label: "Top active concern", value: concerns?.top_active_concern as string },
                    { label: "Active count", value: concerns?.active_concern_count as number },
                    { label: "Reconciliation", value: concerns?.concern_reconciliation_summary as string },
                  ]}
                />
              </Section>
            </>
          )}

          {tab === "memory" && (
            <>
              <h2 className="h2">Memory / continuity</h2>
              <Section title="Strategic continuity">
                <Kv
                  items={[
                    { label: "Summary", value: memory?.strategic_continuity_summary as string },
                    { label: "Relationship summary", value: memory?.relationship_summary as string },
                    { label: "Relationship carryover", value: memory?.relationship_carryover as string },
                    { label: "Maintenance carryover", value: memory?.maintenance_carryover as string },
                    { label: "Unfinished thread?", value: memory?.unfinished_thread_present },
                    { label: "Refined memory class", value: memory?.refined_memory_class as string },
                    { label: "Retrieval priority", value: memory?.refined_memory_retrieval_priority as number },
                    { label: "Memory refinement (tick)", value: memory?.memory_refinement_summary as string },
                  ]}
                />
              </Section>
              <Section title="Active threads">
                <JsonBlock data={memory?.active_threads ?? []} />
              </Section>
              <Section title="Live context">
                <ExpandPre title="live_context (expand)" body={JSON.stringify(memory?.live_context ?? {}, null, 2)} />
              </Section>
            </>
          )}

          {tab === "workbench" && (
            <>
              <h2 className="h2">Workbench</h2>
              <div className="two-col">
                <Section title="Proposals & queue">
                  <Kv
                    items={[
                      { label: "Has proposal", value: wb?.workbench_has_proposal },
                      { label: "Top type", value: wb?.workbench_top_proposal_type as string },
                      { label: "Top title", value: wb?.workbench_top_proposal_title as string },
                      { label: "Summary", value: wb?.workbench_summary as string },
                      { label: "Execution ready", value: wb?.workbench_execution_ready },
                      { label: "Last execution OK", value: wb?.workbench_last_execution_success },
                      { label: "Last execution summary", value: wb?.workbench_last_execution_summary as string },
                    ]}
                  />
                  <ExpandPre title="workbench_meta" body={JSON.stringify(wb?.workbench_meta ?? {}, null, 2)} />
                </Section>
                <Section title="Self-improvement loop">
                  <Kv
                    items={[
                      { label: "Loop active", value: loop?.improvement_loop_active },
                      { label: "Stage", value: loop?.improvement_loop_stage as string },
                      { label: "Loop summary", value: perception?.improvement_loop_summary as string },
                      { label: "Selected proposal id", value: perception?.workbench_selected_proposal_id as string },
                      { label: "Active issue", value: loop?.improvement_active_issue as string },
                      { label: "Awaiting approval", value: loop?.improvement_awaiting_approval },
                      { label: "Last rollback OK", value: perception?.workbench_last_rollback_success },
                    ]}
                  />
                  <ExpandPre title="improvement_loop_meta" body={JSON.stringify(loop?.improvement_loop_meta ?? {}, null, 2)} />
                </Section>
              </div>
              <Section title="Workbench index (live)" muted="Same listing source as Gradio workbench refresh — read-only here.">
                <ExpandPre title="format_workbench_index preview" body={String(wb?.workbench_index_text ?? "")} />
                {wb?.workbench_index_error ? <p className="err-inline">{String(wb.workbench_index_error)}</p> : null}
              </Section>
              <Section title="Global execution / command summaries (host)">
                <Kv
                  items={[
                    { label: "Last execution result", value: wb?.last_execution_global as string },
                    { label: "Last command result", value: wb?.last_command_global as string },
                  ]}
                />
              </Section>
            </>
          )}

          {tab === "identity" && (
            <>
              <h2 className="h2">Self / identity (read-only)</h2>
              <p className="fineprint">Primary anchors under <code>ava_core/</code>. Editing is not enabled in this build.</p>
              <button type="button" onClick={() => void loadIdentity()}>
                Refresh files
              </button>
              <Section title="IDENTITY.md">
                <pre className="identity-pre">{identity.identity}</pre>
              </Section>
              <Section title="SOUL.md">
                <pre className="identity-pre">{identity.soul}</pre>
              </Section>
              <Section title="USER.md">
                <pre className="identity-pre">{identity.user}</pre>
              </Section>
            </>
          )}

          {tab === "debug" && (
            <>
              <h2 className="h2">Debug (human-readable)</h2>
              <Section title="At a glance">
                <Kv items={debugSummary} />
              </Section>
              <div className="two-col">
                <Section title="Heartbeat / runtime">
                  <JsonBlock data={hb} maxHeight={320} />
                </Section>
                <Section title="Models">
                  <JsonBlock data={models} maxHeight={320} />
                </Section>
              </div>
              <Section title="Concerns">
                <Kv
                  items={[
                    { label: "Active count", value: concerns?.active_concern_count as number },
                    { label: "Top concern", value: concerns?.top_active_concern as string },
                    { label: "Reconciliation summary", value: concerns?.concern_reconciliation_summary as string },
                  ]}
                />
                <ExpandPre title="concern_reconciliation_meta" body={JSON.stringify(concerns?.concern_reconciliation_meta ?? {}, null, 2)} />
              </Section>
              <Section title="Reply path meta">
                <JsonBlock data={debugHuman?.reply_path ?? {}} />
              </Section>
            </>
          )}

          {tab === "export" && (
            <>
              <h2 className="h2">Debug export (AI handoff)</h2>
              <p className="fineprint">Dense status blob for ChatGPT / Claude / another assistant. Copy all.</p>
              <button type="button" className="primary" onClick={() => void loadExport()}>
                Refresh export
              </button>
              <textarea className="export-ta" rows={28} readOnly value={exportText} spellCheck={false} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function Chip({ k, v, narrow }: { k: string; v?: unknown; narrow?: boolean }) {
  const s = v !== undefined && v !== null && String(v).trim() ? String(v) : "—";
  return (
    <span className={`chip ${narrow ? "chip-long" : ""}`} title={`${k}: ${s}`}>
      <span className="chip-k">{k}</span>
      <span className="chip-v">{s.length > 56 && narrow ? `${s.slice(0, 54)}…` : s}</span>
    </span>
  );
}
