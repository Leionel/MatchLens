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
  InvestigationSeed,
} from "./components/cockpit/types";
import { TacticalHeader } from "./components/cockpit/TacticalHeader";
import { WorkspaceTabs } from "./components/cockpit/WorkspaceTabs";
import { MatchCenterWorkspace } from "./components/cockpit/MatchCenterWorkspace";
import { TacticalLabWorkspace } from "./components/cockpit/TacticalLabWorkspace";
import { StoryAgentWorkbench } from "./components/cockpit/StoryAgentWorkbench";
import { ValidationLabWorkspace } from "./components/cockpit/ValidationLabWorkspace";
import { MatchLibraryWorkspace } from "./components/cockpit/MatchLibraryWorkspace";
import { ProducerWorkspace } from "./components/cockpit/ProducerWorkspace";
import { InspectorDrawer } from "./components/cockpit/InspectorDrawer";
import { TacticalGuideModal } from "./components/cockpit/TacticalGuideModal";
import { Locale, getTranslation } from "./lib/i18n";

const WORKSPACE_IDS: WorkspaceId[] = [
  "match_hub",
  "match_center",
  "tactical_lab",
  "story_agent",
  "producer",
  "validation_lab",
];

function workspaceFromSearch(search: string): WorkspaceId | null {
  const raw = new URLSearchParams(search).get("workspace");
  return WORKSPACE_IDS.includes(raw as WorkspaceId) ? (raw as WorkspaceId) : null;
}

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
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("match_hub");
  const [perspective, setPerspective] = useState<PerspectiveId>("coach");

  // Selection & Drilldown Cross-Workspace State
  const [selectedEventId, setSelectedEventId] = useState("");
  const [selectedSeqId, setSelectedSeqId] = useState("");
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [activeSmoothingMode, setActiveSmoothingMode] = useState<"causal" | "bilateral">("causal");
  const [investigationSeed, setInvestigationSeed] = useState<InvestigationSeed | null>(null);
  const [globalQuery, setGlobalQuery] = useState("");
  const urlRestored = useRef(false);
  const urlRestoring = useRef(false);
  const [urlRestoreToken, setUrlRestoreToken] = useState(0);
  const seekRequest = useRef(0);
  const smoothingRequest = useRef(0);
  const recoveryRequest = useRef(0);
  const stateRef = useRef<CockpitState | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

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
      const target = e.target as HTMLElement | null;
      // Space belongs to the focused control first. Only a page-level Space
      // (no interactive target, no dialog) is a replay shortcut.
      const interactive = target?.closest(
        "input, textarea, select, button, a, [role='button'], [role='tab'], [role='menuitem'], [contenteditable='true']",
      );
      const dialogOpen = Boolean(document.querySelector("[role='dialog'], [aria-modal='true']"));
      if (e.code === "Space") {
        if (interactive || dialogOpen || e.repeat || e.defaultPrevented) return;
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

  /**
   * One seek at a time. The dock commits on release, so this is also the guard
   * that drops a late response belonging to an older match or clock request.
   */
  const seekTo = async (at: number): Promise<boolean> => {
    const token = ++seekRequest.current;
    const matchId = stateRef.current?.match_id;
    setError("");
    setBusy(true);
    try {
      const next = await api<CockpitState>("control", { action: "seek", at });
      if (token !== seekRequest.current) return false;
      if (matchId && next.match_id !== matchId) return false;
      commit(next);
      // The caller may verify the clock immediately, before React flushes the
      // state updater. Keep the ref as the synchronous source of truth.
      stateRef.current = next;
      return true;
    } catch (e) {
      if (token === seekRequest.current) setError((e as Error).message);
      return false;
    } finally {
      if (token === seekRequest.current) setBusy(false);
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

  const selectMatch = async (
    matchId: string,
    workspace?: WorkspaceId,
    options?: { preserveSeed?: boolean; history?: "push" | "replace" | "none" },
  ) => {
    setError("");
    setBusy(true);
    try {
      const next = await api<CockpitState>("control", { action: "set_match", match_id: matchId });
      commit(next);
      stateRef.current = next;
      setActiveWorkspace(workspace || "match_center");
      setSelectedEventId("");
      setSelectedSeqId("");
      setSelectedPlayerId(null);
      setSelectedZoneId(null);
      if (!options?.preserveSeed) setInvestigationSeed(null);
      if (options?.history !== "none") {
        try {
          const url = new URL(window.location.href);
          url.searchParams.set("workspace", workspace || "match_center");
          url.searchParams.set("match", matchId);
          url.searchParams.delete("event");
          url.searchParams.delete("sequence");
          window.history[options?.history === "replace" ? "replaceState" : "pushState"]({}, "", url);
        } catch {}
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const selectWorkspace = (
    workspace: WorkspaceId,
    options?: { history?: "push" | "replace" | "none"; query?: string },
  ) => {
    setActiveWorkspace(workspace);
    if (options?.history === "none") return;
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("workspace", workspace);
      if (options?.query !== undefined) {
        if (options.query) url.searchParams.set("q", options.query);
        else url.searchParams.delete("q");
      }
      window.history[options?.history === "replace" ? "replaceState" : "pushState"]({}, "", url);
    } catch {}
  };

  const handleSearch = (query: string) => {
    setGlobalQuery(query);
    selectWorkspace("match_hub", { query });
  };

  /**
   * The investigation was opened from a moment of this match. Returning puts
   * the analyst back on that moment in Match Detail, not on an arbitrary clock,
   * so the evidence they just read is still on screen.
   */
  const returnToMatchAt = (at: number) => {
    void (async () => {
      const aligned = await seekTo(at);
      if (!aligned) return;
      selectWorkspace("match_center");
    })();
  };

  const openIntelligence = () => {
    const current = stateRef.current;
    if (!current) return;
    void openInvestigation({
      requestId: `ask-${Date.now()}`,
      matchId: current.match_id || "syn_default",
      team: current.focus_team === "N" ? "N" : "H",
      at: current.snapshot_as_of ?? current.at ?? 0,
      focusType: "moment",
      focusId: null,
      question: "",
    });
  };

  const investigateMoment = (payload: {
    focus_type: "oaai_point";
    focus_id: string;
    at: number;
    team: "H" | "N";
  }) => {
    void openInvestigation({
      requestId: `chart-${payload.focus_id}-${Date.now()}`,
      matchId: stateRef.current?.match_id || "syn_default",
      team: payload.team,
      at: payload.at,
      focusType: "oaai_point",
      focusId: payload.focus_id,
      question: locale === "zh" ? "为什么这个时刻的进攻活动发生变化？" : "What produced this attacking activity change?",
    });
  };

  /**
   * Switch to the intelligence workspace only after the session clock has
   * reached the evidence moment. Otherwise the plan would be computed at a
   * different snapshot than the replay the analyst is looking at.
   */
  const openInvestigation = async (seed: InvestigationSeed) => {
    setError("");
    try {
      const current = stateRef.current;
      if (!current) {
        setError(locale === "zh" ? "比赛数据尚未加载，无法发起调查。" : "Match data is not loaded; the investigation was not started.");
        return;
      }
      if (current.match_id !== seed.matchId) {
        await selectMatch(seed.matchId, "story_agent", {
          preserveSeed: true,
          history: "none",
        });
        if (stateRef.current?.match_id !== seed.matchId) {
          setError(locale === "zh" ? "比赛数据不可用，无法发起调查。" : "Match data is unavailable; the investigation was not started.");
          return;
        }
      }
      // Always align after a match switch: the new match starts at its own
      // clock, never at the evidence moment carried over from the old one.
      const loadedAt = Number(stateRef.current?.snapshot_as_of ?? stateRef.current?.at ?? 0);
      if (Math.abs(loadedAt - seed.at) > 1) {
        const aligned = await seekTo(seed.at);
        if (!aligned) {
          setError(
            locale === "zh"
              ? "无法把回放时钟对齐到该证据时刻，调查未发起。"
              : "Could not align the replay clock to the evidence moment; the investigation was not started.",
          );
          return;
        }
      }
      const aligned = stateRef.current;
      const alignedAt = Number(aligned?.snapshot_as_of ?? aligned?.at ?? 0);
      if (aligned?.match_id !== seed.matchId || Math.abs(alignedAt - seed.at) > 1) {
        setError(
          locale === "zh"
            ? "回放时钟与证据时刻不一致，调查未发起。"
            : "The replay clock does not match the evidence moment; the investigation was not started.",
        );
        return;
      }
      setInvestigationSeed(seed);
      setActiveWorkspace("story_agent");
      try {
        const url = new URL(window.location.href);
        url.searchParams.set("workspace", "story_agent");
        url.searchParams.set("match", seed.matchId);
        url.searchParams.set("at", String(Math.round(seed.at)));
        window.history.pushState({}, "", url);
      } catch {}
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const investigateShot = (payload: {
    matchId: string;
    eventId: string;
    team: "H" | "N";
    at: number;
  }) => {
    void openInvestigation({
      requestId: `shot-${payload.eventId}-${Date.now()}`,
      matchId: payload.matchId,
      team: payload.team,
      at: payload.at,
      focusType: "shot_location",
      focusId: `evt:${payload.eventId}`,
      question:
        locale === "zh"
          ? "这次射门来自怎样的进攻序列？请只陈述已记录证据。"
          : "What recorded attacking sequence produced this shot?",
    });
  };

  /**
   * A player row in Match Detail opens an investigation about that player at
   * the current moment. The player id is the focus, so the plan cites the same
   * recorded events the card counts.
   */
  const investigatePlayer = (payload: {
    player_id: string;
    name: string;
    team: "H" | "N";
  }) => {
    void openInvestigation({
      requestId: `player-${payload.player_id}-${Date.now()}`,
      matchId: stateRef.current?.match_id || "syn_default",
      team: payload.team,
      at: stateRef.current?.snapshot_as_of ?? stateRef.current?.at ?? 0,
      focusType: "player",
      focusId: payload.player_id,
      question:
        locale === "zh"
          ? `${payload.name} 在这场比赛中的已记录动作说明了什么？`
          : `What do ${payload.name}'s recorded actions show in this match?`,
    });
  };

  /**
   * An event row in Match Detail opens an investigation about that event. The
   * replay is aligned to the event's own second first, so the plan cites the
   * snapshot the analyst is looking at.
   */
  const investigateEvent = (payload: { event_id: string; at: number; team: "H" | "N" }) => {
    void openInvestigation({
      requestId: `event-${payload.event_id}-${Date.now()}`,
      matchId: stateRef.current?.match_id || "syn_default",
      team: payload.team,
      at: payload.at,
      focusType: "event",
      focusId: payload.event_id,
      question:
        locale === "zh"
          ? "这次事件前后有哪些已记录动作？请只陈述事件记录。"
          : "Which recorded actions surround this event? State only what the event log records.",
    });
  };

  const investigateCrossMatch = (payload: {
    matchId: string;
    otherMatchId: string;
  }) => {
    void openInvestigation({
      requestId: `cross-${payload.matchId}-${payload.otherMatchId}-${Date.now()}`,
      matchId: payload.matchId,
      team: "H",
      at: state?.snapshot_as_of ?? state?.at ?? 0,
      focusType: "cross_match_diff",
      focusId: "shots",
      compareMatchIds: [payload.otherMatchId],
      question:
        locale === "zh"
          ? "这两场比赛的射门活动差异有哪些证据支持？"
          : "What evidence supports the difference in shot activity between these matches?",
    });
  };

  // Restore workspace, match, clock and selection from a deep link once the
  // first session state is available.
  useEffect(() => {
    if (!state || urlRestored.current) return;
    urlRestored.current = true;
    const params = new URLSearchParams(window.location.search);
    const workspace = workspaceFromSearch(window.location.search);
    if (workspace) {
      setActiveWorkspace(workspace);
    }
    const match = params.get("match");
    const at = params.get("at");
    const event = params.get("event");
    const sequence = params.get("sequence");
    const query = params.get("q") || "";
    if (query) setGlobalQuery(query);
    const restore = async () => {
      urlRestoring.current = true;
      try {
        if (match && match !== state.match_id) {
          await selectMatch(match, workspace || "match_center", { history: "none" });
        }
        if (at !== null && Number.isFinite(Number(at))) {
          await seekTo(Number(at));
        }
        if (event) setSelectedEventId(event);
        if (sequence) setSelectedSeqId(sequence);
      } finally {
        urlRestoring.current = false;
        setUrlRestoreToken((token) => token + 1);
      }
    };
    void restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.match_id]);

  // Keep the URL refreshable without overwriting it during deep-link restore.
  useEffect(() => {
    if (!state || !urlRestored.current || urlRestoring.current) return;
    const url = new URL(window.location.href);
    const anchor = state.paused || state.ended ? state.at : (state.snapshot_as_of ?? state.at);
    url.searchParams.set("workspace", activeWorkspace);
    if (state.match_id) url.searchParams.set("match", state.match_id);
    url.searchParams.set("at", String(anchor));
    if (selectedEventId) url.searchParams.set("event", selectedEventId);
    else url.searchParams.delete("event");
    if (selectedSeqId) url.searchParams.set("sequence", selectedSeqId);
    else url.searchParams.delete("sequence");
    if (globalQuery) url.searchParams.set("q", globalQuery);
    else url.searchParams.delete("q");
    window.history.replaceState({}, "", url);
  }, [activeWorkspace, state?.match_id, state?.at, state?.paused, state?.snapshot_as_of, selectedEventId, selectedSeqId, globalQuery, urlRestoreToken]);

  useEffect(() => {
    const onPopState = () => {
      // A popstate handler must never push another entry. Apply the popped URL
      // directly and let the URL-sync effect replace (not push) afterwards.
      const params = new URLSearchParams(window.location.search);
      const workspace = workspaceFromSearch(window.location.search);
      const match = params.get("match");
      const at = params.get("at");
      const query = params.get("q") || "";
      const apply = async () => {
        urlRestoring.current = true;
        try {
          if (workspace) setActiveWorkspace(workspace);
          setGlobalQuery(query);
          if (match && match !== stateRef.current?.match_id) {
            await selectMatch(match, workspace || "match_center", { history: "none" });
          }
          if (at !== null && Number.isFinite(Number(at))) {
            await seekTo(Number(at));
          }
          setSelectedEventId(params.get("event") || "");
          setSelectedSeqId(params.get("sequence") || "");
        } finally {
          urlRestoring.current = false;
          setUrlRestoreToken((token) => token + 1);
        }
      };
      void apply();
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
    // seekTo/selectMatch use refs for the live session and match.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const inspect = async (id: string, snapshotId?: string) => {
    const request = ++inspectionRequest.current;
    const matchId = stateRef.current?.match_id;
    const target = snapshotId || stateRef.current?.snapshot_id;
    if (!target) return;
    setError("");
    try {
      const data =
        evidence?.snapshot_id === target
          ? evidence
          : await api<Evidence>(`evidence/${target}`);
      if (request !== inspectionRequest.current) return;
      if (matchId && stateRef.current?.match_id !== matchId) return;
      setEvidence(data);
      const rec = data.receipts[id] || stateRef.current?.receipts[id] || null;
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
    const token = ++smoothingRequest.current;
    const matchId = stateRef.current?.match_id;
    const epoch = stateRef.current?.epoch;
    const at = stateRef.current?.snapshot_as_of ?? stateRef.current?.at;
    setActiveSmoothingMode(smoothingMode);
    try {
      const updated = await api<any>(`exploration/oaai?smoothing_mode=${smoothingMode}`);
      if (token !== smoothingRequest.current) return;
      if (updated) {
        setState((prev) =>
          prev &&
          updated.match_id === prev.match_id &&
          updated.match_id === matchId &&
          updated.epoch === epoch &&
          prev.epoch === epoch &&
          (prev.snapshot_as_of ?? prev.at) === at
            ? { ...prev, oaai: updated }
            : prev
        );
      }
    } catch {}
  };

  const handleWindowChange = async (newWindow: number) => {
    const token = ++recoveryRequest.current;
    const matchId = stateRef.current?.match_id;
    const epoch = stateRef.current?.epoch;
    const at = stateRef.current?.snapshot_as_of ?? stateRef.current?.at;
    try {
      const updated = await api<any>(`exploration/recoveries?window_seconds=${newWindow}`);
      if (token !== recoveryRequest.current) return;
      if (updated) {
        setState((prev) =>
          prev &&
          updated.match_id === prev.match_id &&
          updated.match_id === matchId &&
          updated.epoch === epoch &&
          prev.epoch === epoch &&
          (prev.snapshot_as_of ?? prev.at) === at
            ? { ...prev, quick_recoveries: updated }
            : prev
        );
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
          connection={connection}
          theme={theme}
          isDrawerOpen={isDrawerOpen}
          locale={locale}
          query={globalQuery}
          onSearch={handleSearch}
          onOpenHub={() => selectWorkspace("match_hub")}
          onOpenMatch={() => selectWorkspace("match_center")}
          onToggleDrawer={() => setIsDrawerOpen(!isDrawerOpen)}
          onToggleTheme={toggleTheme}
          onToggleLocale={toggleLocale}
          onOpenGuide={() => setIsGuideOpen(true)}
        />
      )}

      {/* 2. Product navigation (public workspaces + professional tools) */}
      {state && (
        <WorkspaceTabs
          activeWorkspace={activeWorkspace}
          onSelectWorkspace={(workspace) => selectWorkspace(workspace)}
          state={state}
          locale={locale}
        />
      )}

      {/* 3. Product Main Layout Area */}
      <div className="cockpit-main-layout r6-main-layout">
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
            <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)" }}>
              {locale === "zh" ? "正在初始化 MatchLens AI 黑曜石战术工作台..." : "Initializing MatchLens AI Obsidian Cockpit..."}
            </h2>
            <p style={{ fontSize: 14, color: "var(--text-secondary)", maxWidth: 500, lineHeight: 1.5 }}>
              {locale === "zh"
                ? "连接确定性实时赛事流，载入 S2 控球推进序列，并载入双智能体审议与发布门禁核验引擎..."
                : "Connecting to real-time deterministic match stream, loading S2 possession sequences, and priming dual-agent deliberation runtime..."}
            </p>
          </div>
        ) : (
          <>
            {(activeWorkspace === "producer" || activeWorkspace === "validation_lab") && (
              <section className="r6-pro-banner" aria-label={locale === "zh" ? "专业工具" : "Professional tools"}>
                <div>
                  <span className="r6-kicker">{locale === "zh" ? "专业工具" : "Professional tools"}</span>
                  <h1>{activeWorkspace === "producer" ? (locale === "zh" ? "转播制作" : "Producer") : locale === "zh" ? "研究与评测" : "Research Lab"}</h1>
                  <p>
                    {activeWorkspace === "producer"
                      ? locale === "zh"
                        ? "审核已过门禁的结论，建立 Rundown，预览并导出可追溯 Manifest。"
                        : "Review gate-approved claims, build a rundown, preview and export a traceable manifest."
                      : locale === "zh"
                        ? "xT 网格、确定性基准与反事实沙盘。研究结论与产品结论严格分层。"
                        : "xT grids, deterministic benchmarks and counterfactual sandbox. Research remains separate from product claims."}
                  </p>
                </div>
                <button type="button" className="r6-text-action" onClick={() => selectWorkspace("match_center")}>
                  {locale === "zh" ? "返回比赛详情 →" : "Back to match detail →"}
                </button>
              </section>
            )}

            {activeWorkspace === "match_hub" && (
              <MatchLibraryWorkspace
                currentMatchId={state.match_id}
                locale={locale}
                initialQuery={globalQuery}
                onQueryChange={setGlobalQuery}
                onSelectMatch={(matchId) => void selectMatch(matchId)}
                onInvestigateShot={investigateShot}
                onInvestigateCrossMatch={investigateCrossMatch}
              />
            )}

            {/* WORKSPACE 1: Match Center */}
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
                busy={busy}
                onSeek={seekTo}
                onControl={control}
                onSelectEvent={(id) => setSelectedEventId(id)}
                onSelectSequence={(seqId) => setSelectedSeqId(seqId)}
                onSelectPlayer={(pid) => setSelectedPlayerId(pid)}
                onSelectZone={(zid) => setSelectedZoneId(zid)}
                onSelectHighlight={(hl) => setSelectedHighlightId(hl.highlight_id)}
                onSelectChannel={(ch) => setSelectedChannel(ch)}
                onToggleSmoothingMode={handleToggleSmoothingMode}
                onOpenInspector={handleOpenInspector}
                onSelectPerspective={setPerspective}
                onOpenIntelligence={openIntelligence}
                onInspectReceipt={(receiptId, snapshotId) => inspect(receiptId, snapshotId)}
                onInvestigateMoment={investigateMoment}
                onInvestigatePlayer={investigatePlayer}
                onInvestigateEvent={investigateEvent}
              />
            )}

            {/* WORKSPACE 2: Tactical & Spatial Lab */}
            {activeWorkspace === "tactical_lab" && (
              <TacticalLabWorkspace
                state={state}
                perspective={perspective}
                selectedEventId={selectedEventId}
                selectedSeqId={selectedSeqId}
                selectedPlayerId={selectedPlayerId}
                selectedZoneId={selectedZoneId}
                locale={locale}
                busy={busy}
                onSeek={seekTo}
                onControl={control}
                onInvestigateFocus={(input) => {
                  void openInvestigation({
                    requestId: `${input.focusType}-${input.focusId}-${Date.now()}`,
                    matchId: state.match_id || "syn_default",
                    team: input.team,
                    at: input.at,
                    focusType: input.focusType,
                    focusId: input.focusId,
                    question:
                      input.focusType === "sequence"
                        ? locale === "zh"
                          ? "这波控球序列由哪些已记录动作构成？"
                          : "Which recorded actions make up this possession sequence?"
                        : locale === "zh"
                          ? "这次事件前后发生了什么？请只陈述已记录证据。"
                          : "What happened around this recorded event?",
                  });
                }}
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
                investigationSeed={investigationSeed}
                onReturnToMatch={returnToMatchAt}
              />
            )}

            {activeWorkspace === "producer" && (
              <ProducerWorkspace state={state} locale={locale} />
            )}

            {/* WORKSPACE 4: Validation Lab */}
            {activeWorkspace === "validation_lab" && (
              <ValidationLabWorkspace
                state={state}
                perspective={perspective}
                locale={locale}
                onOpenInspector={handleOpenInspector}
              />
            )}

            {/* Full-time recap lives inside Match Detail, never in unrelated workspaces. */}
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
        <footer className="cockpit-footer r6-footer" role="contentinfo">
          <div>
            <b>MatchLens</b> · {locale === "zh" ? "足球智能分析" : "Football Intelligence"}
          </div>
          <div>
            {locale === "zh"
              ? "每个结论都可回到记录事件与指标收据；无球阵型与战术因果不会被臆测。"
              : "Every insight returns to recorded events and metric receipts; off-ball shape and tactical cause are never inferred."}
          </div>
        </footer>
      </div>
    </main>
  );
}
