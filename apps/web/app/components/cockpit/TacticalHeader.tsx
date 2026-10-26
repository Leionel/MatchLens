"use client";

import React, { useRef, useState } from "react";
import { CockpitState } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";

interface TacticalHeaderProps {
  state: CockpitState;
  connection: string;
  theme: "dark" | "light";
  isDrawerOpen: boolean;
  locale?: Locale;
  query?: string;
  onSearch: (query: string) => void;
  onOpenHub: () => void;
  onOpenMatch: () => void;
  onToggleDrawer: () => void;
  onToggleTheme: () => void;
  onToggleLocale?: () => void;
  onOpenGuide?: () => void;
}

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
};

/**
 * The global header answers three questions only: where am I, which match is
 * loaded, and where do I search. Replay controls live on the pages that use a
 * timeline, not in every workspace.
 */
export const TacticalHeader: React.FC<TacticalHeaderProps> = ({
  state,
  connection,
  theme,
  isDrawerOpen,
  locale = "zh",
  query: controlledQuery,
  onSearch,
  onOpenHub,
  onOpenMatch,
  onToggleDrawer,
  onToggleTheme,
  onToggleLocale,
  onOpenGuide,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);
  const toolsRef = useRef<HTMLDetailsElement | null>(null);

  const closeTools = () => {
    if (toolsRef.current) toolsRef.current.open = false;
  };

  React.useEffect(() => {
    const closeOnOutside = (event: PointerEvent) => {
      const details = toolsRef.current;
      if (!details?.open || details.contains(event.target as Node)) return;
      details.open = false;
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      const details = toolsRef.current;
      if (event.key !== "Escape" || !details?.open) return;
      details.open = false;
      details.querySelector("summary")?.focus();
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  React.useEffect(() => {
    try {
      const q = new URLSearchParams(window.location.search).get("q");
      if (q) setQuery(q);
    } catch {}
  }, []);

  // The header owns the only search field; the hub's query chip reflects it.
  React.useEffect(() => {
    if (controlledQuery !== undefined) setQuery(controlledQuery);
  }, [controlledQuery]);

  React.useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    onSearch(query.trim());
  };

  const home = state.teams?.H || "Home";
  const away = state.teams?.N || "Away";
  const connected = connection === "Connected" || connection === "Polling";
  // A recorded match replayed along its own clock is not a live feed. The
  // label says which kind of stream this is, from the match's declared source.
  const replayLabel = connected
    ? state.match_id?.startsWith("syn_") || state.match_context?.provenance_kind === "synthetic"
      ? isZh
        ? "模拟回放"
        : "Simulated replay"
      : isZh
        ? "历史回放"
        : "Historical replay"
    : connection;

  return (
    <header className="r6-topbar" role="banner">
      <div className="r6-topbar-inner">
        <button type="button" className="r6-brand" onClick={onOpenHub} title={isZh ? "返回比赛库" : "Back to match hub"}>
          <span className="r6-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <rect x="4" y="6" width="24" height="20" rx="4" stroke="currentColor" strokeWidth="1.8" />
              <path d="M16 6v20M4 16h24" stroke="currentColor" strokeWidth="1.4" opacity=".5" />
              <circle cx="16" cy="16" r="4.4" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          </span>
          <span className="r6-brand-copy">
            <span className="r6-brand-word">
              Match<span>Lens</span>
            </span>
            <span className="r6-brand-sub">FOOTBALL INTELLIGENCE</span>
          </span>
        </button>

        <form className="r6-search" role="search" onSubmit={submit}>
          <span aria-hidden="true">⌕</span>
          <input
            ref={inputRef}
            id="r6-global-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={isZh ? "搜索比赛、球队、赛事…" : "Search matches, teams, competitions…"}
            aria-label={isZh ? "搜索比赛" : "Search matches"}
          />
          <kbd>/</kbd>
        </form>

        <button
          type="button"
          className="r6-current-match"
          onClick={onOpenMatch}
          data-testid="header-current-match"
          title={isZh ? "打开当前比赛详情" : "Open current match detail"}
        >
          <span className="r6-current-comp">
            {state.match_context?.competition || (isZh ? "当前比赛" : "Current match")}
            {state.match_context?.season ? ` · ${state.match_context.season}` : ""}
          </span>
          <span className="r6-current-line">
            <b>{home}</b>
            <strong>
              {state.score?.H ?? 0} – {state.score?.N ?? 0}
            </strong>
            <b>{away}</b>
            <em>{clock(state.at ?? 0)}</em>
          </span>
          <span className="r6-current-status">
            <i className={connected ? "ok" : "warn"} aria-hidden="true" />
            {replayLabel}
          </span>
        </button>

        <div className="r6-top-actions">
          {onOpenGuide && (
            <button type="button" className="r6-icon-button" onClick={onOpenGuide} aria-label={isZh ? "指标释义" : "Indicator guide"} title={isZh ? "指标释义" : "Indicator guide"}>
              i
            </button>
          )}
          {onToggleLocale && (
            <button type="button" className="r6-top-text" onClick={onToggleLocale} aria-label={isZh ? "切换语言" : "Switch language"}>
              {locale === "zh" ? "EN" : "中"}
            </button>
          )}
          <button
            type="button"
            className="r6-top-text r6-theme-toggle"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "LIGHT" : "DARK"}
            title={isZh ? "明暗主题" : "Theme"}
          >
            {theme === "dark" ? "☀ LIGHT" : "☾ DARK"}
          </button>
          <button
            type="button"
            className={`r6-top-text ${isDrawerOpen ? "active" : ""}`}
            onClick={onToggleDrawer}
            aria-expanded={isDrawerOpen}
            aria-label={isZh ? "打开证据检查器" : "Open evidence inspector"}
          >
            {isZh ? "证据" : "Evidence"}
          </button>

          <details className="r6-mobile-tools" ref={toolsRef}>
            <summary className="r6-icon-button r6-tools-summary" data-testid="mobile-tools-trigger">
              {isZh ? "更多" : "More"}
            </summary>
            <div className="r6-tools-menu" data-testid="mobile-tools-menu">
              {onToggleLocale && (
                <button
                  type="button"
                  onClick={() => {
                    onToggleLocale();
                    closeTools();
                  }}
                >
                  {isZh ? "切换为 English" : "切换为中文"}
                </button>
              )}
              {onOpenGuide && (
                <button
                  type="button"
                  onClick={() => {
                    onOpenGuide();
                    closeTools();
                  }}
                >
                  {isZh ? "指标释义" : "Indicator guide"}
                </button>
              )}
              <button
                type="button"
                aria-expanded={isDrawerOpen}
                onClick={() => {
                  onToggleDrawer();
                  closeTools();
                }}
              >
                {isZh ? "证据检查器" : "Evidence inspector"}
              </button>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
};
