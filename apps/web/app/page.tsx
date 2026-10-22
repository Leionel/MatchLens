"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  CockpitState,
  WorkspaceId,
  PerspectiveId,
  InspectorPayload,
  Evidence,
  Receipt,
  PossessionSequence,
} from "./components/cockpit/types";
import { TacticalHeader } from "./components/cockpit/TacticalHeader";
import { WorkspaceTabs } from "./components/cockpit/WorkspaceTabs";
import { MatchCenterWorkspace } from "./components/cockpit/MatchCenterWorkspace";
import { TacticalLabWorkspace } from "./components/cockpit/TacticalLabWorkspace";
import { StoryAgentWorkbench } from "./components/cockpit/StoryAgentWorkbench";
import { ValidationLabWorkspace } from "./components/cockpit/ValidationLabWorkspace";
import { InspectorDrawer } from "./components/cockpit/InspectorDrawer";
import { TacticalGuideModal } from "./components/cockpit/TacticalGuideModal";
import { MatchRecap } from "./components/MatchRecap";
import { Locale, getTranslation } from "./lib/i18n";

async function api<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const errors: Record<number, string> = {
      401: "Your session expired. Refresh to start a new match.",
      409: "Please exit focus or select a valid moment to continue.",
      429: "Analysis limit reached. Please wait a moment before trying again.",
      503: "The demo server is currently busy. Please retry shortly.",
    };
    throw Object.assign(
      new Error(errors[response.status] || `Request failed (${response.status})`),
      { status: response.status }
    );
  }
  return response.json();
}

export default function MatchLensCockpit() {
  const [state, setState] = useState<CockpitState | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("Connecting");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [busy, setBusy] = useState(false);

  // Multi-Pane Cockpit Navigation & Perspective
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("match_center");
  const [perspective, setPerspective] = useState<PerspectiveId>("coach");

  // Selection & Drilldown Cross-Workspace State
  const [selectedEventId, setSelectedEventId] = useState("");
  const [selectedSeqId, setSelectedSeqId] = useState("");
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [activeSmoothingMode, setActiveSmoothingMode] = useState<"causal" | "bilateral">("causal");

  // Collapsible Inspector Sidecar Drawer
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [inspectorPayload, setInspectorPayload] = useState<InspectorPayload | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const inspectionRequest = useRef(0);

  // Theme & Language Initialization & Sync
  const [locale, setLocale] = useState<Locale>("zh");
  const [isGuideOpen, setIsGuideOpen] = useState(false);

  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem("matchlens-theme");
      if (savedTheme === "light" || savedTheme === "dark") {
        setTheme(savedTheme);
        document.documentElement.setAttribute("data-theme", savedTheme);
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
      }
    } catch {}

    try {
      const savedLocale = localStorage.getItem("matchlens-locale");
      if (savedLocale === "zh" || savedLocale === "en") {
        setLocale(savedLocale);
      }
    } catch {}
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("matchlens-theme", next);
    } catch {}
  };

  const toggleLocale = () => {
    const next = locale === "zh" ? "en" : "zh";
    setLocale(next);
    try {
      localStorage.setItem("matchlens-locale", next);
    } catch {}
  };

  // State commit with epoch/revision ordering
  const commit = useCallback((next: CockpitState) => {
    setState((old) =>
      !old || next.epoch > old.epoch || (next.epoch === old.epoch && next.revision >= old.revision)
        ? next
        : old
    );
  }, []);

  // Reset drilldown states when epoch changes (e.g. restart/scenario switch)
  useEffect(() => {
    inspectionRequest.current += 1;
    setEvidence(null);
    setSelectedEventId("");
    setSelectedSeqId("");
    setSelectedPlayerId(null);
    setSelectedZoneId(null);
    setSelectedHighlightId(null);
    setSelectedChannel(null);
    setIsDrawerOpen(false);
    setInspectorPayload(null);
  }, [state?.epoch]);

  // Keyboard shortcuts (Space = Play/Pause, Esc = Close Drawer)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "SELECT" || target.tagName === "TEXTAREA") {
        return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        if (state && !busy && !state.ended) {
          control({ action: state.paused ? "play" : "pause" });
        }
      } else if (e.code === "Escape") {
        if (isDrawerOpen) {
          setIsDrawerOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [state, busy, isDrawerOpen]);

  // SSE Stream and Session Lifecycle
  useEffect(() => {
    let closed = false;
    let stream: EventSource | undefined;
    let poll: ReturnType<typeof setInterval> | undefined;

    api<CockpitState>("sessions", {})
      .then((initial) => {
        if (closed) return;
        commit(initial);
        stream = new EventSource("/api/stream");
        stream.onopen = () => {
          if (!closed) setConnection("Connected");
          if (poll) {
            clearInterval(poll);
            poll = undefined;
          }
        };
        stream.addEventListener("state", (event: MessageEvent) => {
          if (!closed) {
            commit(JSON.parse(event.data));
            setConnection("Connected");
          }
        });
        stream.onerror = () => {
          if (!closed) setConnection("Reconnecting");
          if (!poll) {
            poll = setInterval(() => {
              api<CockpitState>("state")
                .then((next) => {
                  if (!closed) {
                    commit(next);
                    setConnection("Polling");
                  }
                })
                .catch((e) => {
                  if (!closed) {
                    setError(e.message);
                    if (e.status === 401) {
                      stream?.close();
                      if (poll) {
                        clearInterval(poll);
                        poll = undefined;
                      }
                      setConnection("Session expired");
                    }
                  }
                });
            }, 2000);
          }
        };
      })
      .catch((e) => {
        if (!closed) {
          setError(e.message);
          setConnection("Unavailable");
        }
      });

    return () => {
      closed = true;
      stream?.close();
      if (poll) clearInterval(poll);
    };
  }, [commit]);

  // API Actions
  const control = async (body: object) => {
    setError("");
    setBusy(true);
    try {
      commit(await api<CockpitState>("control", body));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const analyse = async () => {
    setError("");
    setBusy(true);
    try {
      commit(await api<CockpitState>("analyse", {}));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const inspect = async (id: string, snapshotId?: string) => {
    const request = ++inspectionRequest.current;
    const target = snapshotId || state?.snapshot_id;
    if (!target) return;
    setError("");
    try {
      const data =
        evidence?.snapshot_id === target
          ? evidence
          : await api<Evidence>(`evidence/${target}`);
      if (request !== inspectionRequest.current) return;
      setEvidence(data);
      const rec = data.receipts[id] || state?.receipts[id] || null;
      setInspectorPayload({
        type: "receipt",
        receiptId: id,
        receipt: rec,
        title: `Metric Receipt: ${id}`,
      });
      if (rec?.event_ids?.length) {
        setSelectedEventId(rec.event_ids.at(-1)!);
      }
      setIsDrawerOpen(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleToggleSmoothingMode = async (smoothingMode: "causal" | "bilateral") => {
    setActiveSmoothingMode(smoothingMode);
    try {
      const updated = await api<any>(`exploration/oaai?smoothing_mode=${smoothingMode}`);
      if (updated) {
        setState((prev) => (prev ? { ...prev, oaai: updated } : prev));
      }
    } catch {}
  };

  const handleWindowChange = async (newWindow: number) => {
    try {
      const updated = await api<any>(`exploration/recoveries?window_seconds=${newWindow}`);
      if (updated) {
        setState((prev) => (prev ? { ...prev, quick_recoveries: updated } : prev));
      }
    } catch {}
  };

  // Open inspector helper
  const handleOpenInspector = (payload: InspectorPayload) => {
    setInspectorPayload(payload);
    setIsDrawerOpen(true);
  };

  return (
    <main className="matchlens-app-root" style={{ background: "var(--pitch-bg)", minHeight: "100vh" }}>
      {/* 1. Tactical Header (Top Control Center) */}
      {state && (
        <TacticalHeader
          state={state}
          busy={busy}
          perspective={perspective}
          connection={connection}
          theme={theme}
          isDrawerOpen={isDrawerOpen}
          locale={locale}
          onToggleDrawer={() => setIsDrawerOpen(!isDrawerOpen)}
          onToggleTheme={toggleTheme}
          onToggleLocale={toggleLocale}
          onOpenGuide={() => setIsGuideOpen(true)}
          onSelectPerspective={(p) => setPerspective(p)}
          onControl={control}
        />
      )}

      {/* 2. Workspace Tabs Navigation */}
      {state && (
        <WorkspaceTabs
          activeWorkspace={activeWorkspace}
          onSelectWorkspace={(ws) => setActiveWorkspace(ws)}
          state={state}
          locale={locale}
        />
      )}

      {/* 3. Cockpit Main Layout Area */}
      <div className="cockpit-main-layout">
        {/* Global Error Toast */}
        {error && (
          <div className="cockpit-toast-bar" role="alert">
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setError("")}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--crimson-warn)",
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 14,
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Loading State before SSE Connects */}
        {!state ? (
          <div
            className="initial-loading-card"
            role="status"
            style={{
              padding: "80px 20px",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 16,
            }}
          >
            <div className="loader-ring" />
            <h2 style={{ fontSize: 20, fontWeight: 800, color: "var(--text-primary)" }}>
              {locale === "zh" ? "正在初始化 MatchLens AI 黑曜石战术工作台..." : "Initializing MatchLens AI Obsidian Cockpit..."}
            </h2>
            <p style={{ fontSize: 13, color: "var(--text-secondary)", maxWidth: 500, lineHeight: 1.5 }}>
              {locale === "zh"
                ? "连接确定性实时赛事流，载入 S2 控球推进序列，并预热三智能体审议与 Gate 2.0 核验引擎..."
                : "Connecting to real-time deterministic match stream, loading S2 possession sequences, and priming dual-agent deliberation runtime..."}
            </p>
          </div>
        ) : (
          <>
            {/* WORKSPACE 1: 🏟️ Match Center */}
            {activeWorkspace === "match_center" && (
              <MatchCenterWorkspace
                state={state}
                perspective={perspective}
                selectedEventId={selectedEventId}
                selectedSeqId={selectedSeqId}
                selectedPlayerId={selectedPlayerId}
                selectedZoneId={selectedZoneId}
                selectedHighlightId={selectedHighlightId}
                selectedChannel={selectedChannel}
                activeSmoothingMode={activeSmoothingMode}
                locale={locale}
                onSeek={(t) => control({ action: "seek", at: t })}
                onSelectEvent={(id) => setSelectedEventId(id)}
                onSelectSequence={(seqId) => setSelectedSeqId(seqId)}
                onSelectPlayer={(pid) => setSelectedPlayerId(pid)}
                onSelectZone={(zid) => setSelectedZoneId(zid)}
                onSelectHighlight={(hl) => setSelectedHighlightId(hl.highlight_id)}
                onSelectChannel={(ch) => setSelectedChannel(ch)}
                onToggleSmoothingMode={handleToggleSmoothingMode}
                onOpenInspector={handleOpenInspector}
              />
            )}

            {/* WORKSPACE 2: 🧭 Tactical & Spatial Lab */}
            {activeWorkspace === "tactical_lab" && (
              <TacticalLabWorkspace
                state={state}
                perspective={perspective}
                selectedEventId={selectedEventId}
                selectedSeqId={selectedSeqId}
                selectedPlayerId={selectedPlayerId}
                selectedZoneId={selectedZoneId}
                locale={locale}
                onSelectEvent={(id: string) => setSelectedEventId(id)}
                onSelectSequence={(seqId: string) => setSelectedSeqId(seqId)}
                onSelectPlayer={(pid: string | null) => setSelectedPlayerId(pid)}
                onSelectZone={(zid: string | null) => setSelectedZoneId(zid)}
                onWindowChange={handleWindowChange}
                onInspectReceipt={(id: string) => inspect(id)}
                onOpenInspector={handleOpenInspector}
              />
            )}

            {/* WORKSPACE 3: 🤖 Story & Agent Workbench */}
            {activeWorkspace === "story_agent" && (
              <StoryAgentWorkbench
                state={state}
                perspective={perspective}
                busy={busy}
                analysesRemaining={state.session_analyses_remaining}
                locale={locale}
                onAnalyse={analyse}
                onInspectReceipt={(id, sId) => inspect(id, sId)}
                onSelectEvent={(id) => setSelectedEventId(id)}
                onOpenInspector={handleOpenInspector}
                onCommitState={(next) => commit(next)}
              />
            )}

            {/* WORKSPACE 4: 📊 Validation Lab */}
            {activeWorkspace === "validation_lab" && (
              <ValidationLabWorkspace
                state={state}
                perspective={perspective}
                locale={locale}
                onOpenInspector={handleOpenInspector}
              />
            )}

            {/* Full-Time Dossier when match finishes */}
            {state.ended && (
              <div style={{ marginTop: 24 }}>
                <MatchRecap
                  score={state.score}
                  history={state.history}
                  locale={locale}
                  onInspect={(rId, sId) => inspect(rId, sId)}
                />
              </div>
            )}
          </>
        )}

        {/* 4. Collapsible Non-Blocking Inspector Drawer */}
        <InspectorDrawer
          isOpen={isDrawerOpen}
          onClose={() => setIsDrawerOpen(false)}
          payload={inspectorPayload}
          evidence={evidence}
          players={state?.players}
          locale={locale}
          onSelectEvent={(id) => setSelectedEventId(id)}
          onSelectSequence={(seqId) => setSelectedSeqId(seqId)}
          onInspectReceipt={(id) => inspect(id)}
        />

        {/* 5. Tactical Indicators & Glossary Guide Modal */}
        <TacticalGuideModal
          isOpen={isGuideOpen}
          onClose={() => setIsGuideOpen(false)}
          locale={locale}
        />

        {/* Cockpit Footer */}
        <footer className="cockpit-footer" role="contentinfo">
          <div>
            <b style={{ color: "var(--text-primary)" }}>MatchLens AI Cockpit 4.0</b> · {locale === "zh" ? "黑曜石战术暗夜架构" : "Obsidian Tactical Dark Architecture"}
          </div>
          <div>
            {locale === "zh"
              ? "确定性事件流 · SHA-256 可核验证据凭证 · Gate 2.0 三智能体协作研报"
              : "Deterministic Event Stream · SHA-256 Verifiable Receipts · Gate 2.0 Tri-Agent Intelligence"}
          </div>
        </footer>
      </div>
    </main>
  );
}
