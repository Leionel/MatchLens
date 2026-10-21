"use client";

import React from "react";
import { CockpitState, PerspectiveId } from "./types";

interface TacticalHeaderProps {
  state: CockpitState;
  busy: boolean;
  perspective: PerspectiveId;
  connection: string;
  theme: "dark" | "light";
  isDrawerOpen: boolean;
  onToggleDrawer: () => void;
  onToggleTheme: () => void;
  onSelectPerspective: (p: PerspectiveId) => void;
  onControl: (body: object) => void;
}

const clock = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;

export const TacticalHeader: React.FC<TacticalHeaderProps> = ({
  state,
  busy,
  perspective,
  connection,
  theme,
  isDrawerOpen,
  onToggleDrawer,
  onToggleTheme,
  onSelectPerspective,
  onControl,
}) => {
  const currentSeconds = state.at || 0;
  const totalSeconds = 720; // 12-minute match simulation window
  const activeMoment = state.active_moment;

  return (
    <header className="cockpit-header" role="banner">
      <div className="cockpit-header-inner">
        {/* Brand & System Badges */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <a href="/" className="cockpit-brand" aria-label="MatchLens AI Home">
            <svg
              viewBox="0 0 32 32"
              style={{
                width: 26,
                height: 26,
                fill: "none",
                stroke: "var(--turf-emerald)",
                strokeWidth: 2.2,
              }}
              aria-hidden="true"
            >
              <circle cx="14" cy="14" r="10" />
              <circle cx="14" cy="14" r="3" />
              <path d="M21 21L29 29 M4 14H8 M20 14H24 M14 4V8 M14 20V24" />
            </svg>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
              <span style={{ fontSize: 18, fontWeight: 900, letterSpacing: -0.5, color: "var(--text-primary)" }}>
                MATCHLENS
              </span>
              <span style={{ fontSize: 12, fontWeight: 900, color: "var(--turf-emerald)" }}>AI</span>
            </div>
          </a>

          <span className="cockpit-brand-badge" title="Obsidian Tactical Multi-Pane Cockpit Engine">
            <span className="pulse-indicator" />
            <span>COCKPIT 4.0</span>
          </span>
        </div>

        {/* Match Switcher Dropdown */}
        <div className="match-selector-wrap" title="Select Match Archetype or Real Scenario">
          <label htmlFor="cockpit-match-select" style={{ fontSize: 11, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
            Match
          </label>
          <select
            id="cockpit-match-select"
            className="match-selector-select"
            value={state.scenario || "default"}
            disabled={busy}
            onChange={(e) => onControl({ action: "set_scenario", scenario: e.target.value })}
          >
            {(state.scenarios && state.scenarios.length > 0) ? (
              state.scenarios.map((sc) => (
                <option key={sc.id} value={sc.id}>
                  {sc.label} ({sc.archetype})
                </option>
              ))
            ) : (
              <>
                <option value="default">Harbor FC vs Northbridge (Default)</option>
                <option value="comeback">Harbor FC vs Northbridge (Comeback)</option>
                <option value="counter">Harbor FC vs Northbridge (Counter)</option>
              </>
            )}
            <option value="sb_wc2022_final">FIFA World Cup Final 2022 (ARG 3-3 FRA)</option>
          </select>
        </div>

        {/* Global Timeline Scrubber Cluster */}
        <div className="header-scrubber-cluster" aria-label="Global Replay Scrubber">
          <button
            type="button"
            className="header-play-btn"
            disabled={busy || state.ended}
            onClick={() => onControl({ action: state.paused ? "play" : "pause" })}
            title={state.paused ? "Play match (Space)" : "Pause match (Space)"}
          >
            {state.paused ? "▶" : "⏸"}
          </button>

          <button
            type="button"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary)",
              cursor: "pointer",
              fontSize: 14,
              padding: "4px",
              minHeight: "auto",
            }}
            disabled={busy}
            onClick={() => onControl({ action: "restart" })}
            title="Restart replay from kickoff"
          >
            ↺
          </button>

          <span className="header-clock-display">{clock(currentSeconds)}</span>

          <input
            type="range"
            min={0}
            max={totalSeconds}
            value={currentSeconds}
            disabled={busy}
            onChange={(e) => onControl({ action: "seek", at: Number(e.target.value) })}
            className="header-slider"
            title={`Seek: ${clock(currentSeconds)} / ${clock(totalSeconds)}`}
          />

          {/* Speed Pills */}
          <div style={{ display: "flex", gap: 3 }}>
            {([1, 6, 30] as const).map((spd) => (
              <button
                key={spd}
                type="button"
                className={`header-speed-pill ${state.speed === spd ? "active" : ""}`}
                disabled={busy}
                onClick={() => onControl({ action: "speed", speed: spd })}
                title={`Playback speed ${spd}x`}
              >
                {spd}×
              </button>
            ))}
          </div>

          {activeMoment && (
            <span
              style={{
                fontSize: 11,
                fontWeight: 750,
                color: "var(--amber-gold)",
                background: "rgba(245, 158, 11, 0.15)",
                padding: "2px 6px",
                borderRadius: 4,
                border: "1px solid rgba(245, 158, 11, 0.3)",
              }}
            >
              {activeMoment.badge}
            </span>
          )}
        </div>

        {/* Perspective Switcher (Coach, Media, Fan) */}
        <div className="perspective-segmented-ctrl" role="group" aria-label="User Perspective Profile">
          <button
            type="button"
            className={`perspective-btn perspective-coach ${perspective === "coach" ? "active" : ""}`}
            onClick={() => onSelectPerspective("coach")}
            title="Coach & Tactical Analyst: High-density channels, 6s recoveries, and ΔD(z)"
          >
            <span>👔</span>
            <span>Coach/Tactics</span>
          </button>

          <button
            type="button"
            className={`perspective-btn perspective-media ${perspective === "media" ? "active" : ""}`}
            onClick={() => onSelectPerspective("media")}
            title="Broadcast & Media: Momentum tidal waves, turning point chapters, and automated narrative"
          >
            <span>🎙️</span>
            <span>Broadcast/Media</span>
          </button>

          <button
            type="button"
            className={`perspective-btn perspective-fan ${perspective === "fan" ? "active" : ""}`}
            onClick={() => onSelectPerspective("fan")}
            title="Deep Fan: Star player tracking, key shots, and exciting team sequences"
          >
            <span>⚽</span>
            <span>Deep Fan</span>
          </button>
        </div>

        {/* Right Tools: Connection, Theme, Inspector Drawer Toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            className={`connection-pill ${connection === "Connected" ? "connected" : ""}`}
            style={{ fontSize: 11, padding: "3px 8px" }}
          >
            <i className="status-dot" />
            <span>{connection}</span>
          </span>

          <button
            type="button"
            onClick={onToggleTheme}
            style={{
              minHeight: 32,
              padding: "4px 8px",
              fontSize: 12,
              background: "transparent",
              border: "1px solid var(--pitch-border)",
              borderRadius: 6,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
            title={`Toggle ${theme === "dark" ? "Light" : "Dark"} mode`}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>

          <button
            type="button"
            onClick={onToggleDrawer}
            style={{
              minHeight: 32,
              padding: "4px 10px",
              fontSize: 12,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 7,
              background: isDrawerOpen ? "rgba(56, 189, 248, 0.2)" : "rgba(15, 23, 42, 0.8)",
              border: `1px solid ${isDrawerOpen ? "var(--tech-cyan)" : "var(--glass-border)"}`,
              color: isDrawerOpen ? "var(--tech-cyan)" : "var(--text-primary)",
              cursor: "pointer",
            }}
            title="Toggle Non-blocking Tactical Inspector Drawer"
          >
            <span>🔍</span>
            <span>Inspector</span>
            {isDrawerOpen && <span style={{ fontSize: 10 }}>●</span>}
          </button>
        </div>
      </div>
    </header>
  );
};
