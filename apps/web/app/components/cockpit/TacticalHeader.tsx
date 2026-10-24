"use client";

import React from "react";
import { CockpitState, PerspectiveId } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";

interface TacticalHeaderProps {
  state: CockpitState;
  busy: boolean;
  perspective: PerspectiveId;
  connection: string;
  theme: "dark" | "light";
  isDrawerOpen: boolean;
  locale?: Locale;
  onToggleDrawer: () => void;
  onToggleTheme: () => void;
  onToggleLocale?: () => void;
  onOpenGuide?: () => void;
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
  locale = "zh",
  onToggleDrawer,
  onToggleTheme,
  onToggleLocale,
  onOpenGuide,
  onSelectPerspective,
  onControl,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  const currentSeconds = state.at || 0;
  const totalSeconds = state.format_seconds || 720;
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
                {t.brandTitle}
              </span>
              <span style={{ fontSize: 12, fontWeight: 900, color: "var(--text-emerald)" }}>AI</span>
            </div>
          </a>

          <span className="cockpit-brand-badge" title="Obsidian Tactical Multi-Pane Cockpit Engine">
            <span className="pulse-indicator" />
            <span>{t.cockpitVersion}</span>
          </span>
        </div>

        {/* Match Switcher Dropdown */}
        <div className="match-selector-wrap" title="Select Match Archetype or Real Scenario">
          <label htmlFor="cockpit-match-select" style={{ fontSize: 12, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
            {t.matchLabel}
          </label>
          <select
            id="cockpit-match-select"
            className="match-selector-select"
            value={state.match_id === "sb_wc2022_final" ? "sb_wc2022_final" : state.scenario || "default"}
            disabled={busy}
            onChange={(e) => {
              const val = e.target.value;
              if (val.startsWith("sb_")) {
                onControl({ action: "set_match", match_id: val });
              } else {
                onControl({ action: "set_scenario", scenario: val });
              }
            }}
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
            title={state.paused ? `${t.playMatch} (Space)` : `${t.pauseMatch} (Space)`}
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
            title={t.restartKickoff}
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
                title={`${t.playbackSpeed} ${spd}x`}
              >
                {spd}×
              </button>
            ))}
          </div>

          {activeMoment && (
            <span
              style={{
                fontSize: 12,
                fontWeight: 750,
                color: "var(--text-gold)",
                background: "color-mix(in srgb, var(--amber-9) 15%, transparent)",
                padding: "2px 6px",
                borderRadius: 4,
                border: "0.5px solid color-mix(in srgb, var(--amber-9) 30%, transparent)",
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
            title={t.perspectiveCoachDesc}
          >
            <span className="perspective-key">C</span>
            <span>{isZh ? "教练视角" : "Coach"}</span>
          </button>

          <button
            type="button"
            className={`perspective-btn perspective-media ${perspective === "media" ? "active" : ""}`}
            onClick={() => onSelectPerspective("media")}
            title={t.perspectiveMediaDesc}
          >
            <span className="perspective-key">M</span>
            <span>{isZh ? "转播视角" : "Media"}</span>
          </button>

          <button
            type="button"
            className={`perspective-btn perspective-fan ${perspective === "fan" ? "active" : ""}`}
            onClick={() => onSelectPerspective("fan")}
            title={t.perspectiveFanDesc}
          >
            <span className="perspective-key">F</span>
            <span>{isZh ? "球迷视角" : "Deep Fan"}</span>
          </button>
        </div>

        {/* Right Tools: Guide Modal Button, Language Switcher, Theme, Inspector Drawer Toggle */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Tactical Guide / Help Docs Button */}
          {onOpenGuide && (
            <button
              type="button"
              onClick={onOpenGuide}
              style={{
                minHeight: 32,
                padding: "4px 10px",
                fontSize: 12,
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: 5,
                borderRadius: 6,
                background: "color-mix(in srgb, var(--amber-9) 12%, transparent)",
                border: "0.5px solid color-mix(in srgb, var(--amber-9) 30%, transparent)",
                color: "var(--text-gold)",
                cursor: "pointer",
              }}
              title={isZh ? "打开指标与战术指南释义字典" : "Open Tactical Indicator Documentation"}
            >
              <span className="tool-key">i</span>
              <span>{isZh ? "指标释义" : "Guide"}</span>
            </button>
          )}

          {/* Language Switcher Button (中 / EN) */}
          {onToggleLocale && (
            <button
              type="button"
              onClick={onToggleLocale}
              style={{
                minHeight: 32,
                padding: "4px 9px",
                fontSize: 12,
                fontWeight: 800,
                borderRadius: 6,
                background: "color-mix(in srgb, var(--cyan-9) 12%, transparent)",
                border: "0.5px solid color-mix(in srgb, var(--cyan-9) 30%, transparent)",
                color: "var(--text-cyan)",
                cursor: "pointer",
                letterSpacing: "0.5px",
              }}
              title={isZh ? "Switch to English" : "切换为中文"}
            >
              {isZh ? "EN" : "中文"}
            </button>
          )}

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={onToggleTheme}
            style={{
              minHeight: 32,
              padding: "4px 8px",
              fontSize: 12,
              background: "transparent",
              border: "0.5px solid var(--pitch-border)",
              borderRadius: 6,
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
            title={theme === "dark" ? t.themeLight : t.themeDark}
          >
            {theme === "dark" ? "LIGHT" : "DARK"}
          </button>

          {/* Inspector Drawer Toggle */}
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
              background: isDrawerOpen ? "color-mix(in srgb, var(--cyan-9) 20%, transparent)" : "color-mix(in srgb, var(--slate-1) 80%, transparent)",
              border: `0.5px solid ${isDrawerOpen ? "var(--tech-cyan)" : "var(--glass-border)"}`,
              color: isDrawerOpen ? "var(--tech-cyan)" : "var(--text-primary)",
              cursor: "pointer",
            }}
            title={t.inspectorDrawer}
          >
            
            <span>{t.inspectorDrawer}</span>
            {isDrawerOpen && <span style={{ fontSize: 12 }}>●</span>}
          </button>
        </div>
      </div>
    </header>
  );
};
