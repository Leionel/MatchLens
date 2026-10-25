"use client";

import React, { useEffect, useRef, useState } from "react";
import { CockpitState, WorkspaceId } from "./types";
import { Locale } from "../../lib/i18n";

interface WorkspaceTabsProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (id: WorkspaceId) => void;
  state: CockpitState;
  locale?: Locale;
}

type PublicTab = {
  id: WorkspaceId;
  zh: string;
  en: string;
  hintZh: string;
  hintEn: string;
  badge: (state: CockpitState) => string;
};

const PUBLIC_TABS: PublicTab[] = [
  {
    id: "match_hub",
    zh: "比赛库",
    en: "Match Hub",
    hintZh: "发现并选择比赛",
    hintEn: "Find a match",
    badge: () => "",
  },
  {
    id: "match_center",
    zh: "比赛详情",
    en: "Match Detail",
    hintZh: "比分、趋势与 AI 洞察",
    hintEn: "Score, trend and AI insight",
    badge: (state) => `${state.score?.H ?? 0}–${state.score?.N ?? 0}`,
  },
  {
    id: "tactical_lab",
    zh: "战术探索",
    en: "Tactical Explorer",
    hintZh: "球场、序列与空间",
    hintEn: "Pitch, sequences and space",
    badge: (state) => `${state.sequences?.length || 0}`,
  },
  {
    id: "story_agent",
    zh: "智能调查",
    en: "Intelligence Studio",
    hintZh: "带着证据提问",
    hintEn: "Ask with evidence",
    badge: (state) => `${(state.result?.accepted?.length || 0) + (state.history?.length || 0)}`,
  },
];

const PRO_TOOLS = [
  { id: "producer" as WorkspaceId, zh: "转播制作", en: "Producer", hintZh: "审核、Rundown 与导出", hintEn: "Review, rundown and export" },
  { id: "validation_lab" as WorkspaceId, zh: "研究与评测", en: "Research Lab", hintZh: "xT、基准与反事实沙盘", hintEn: "xT, benchmarks and what-if" },
];

export const WorkspaceTabs: React.FC<WorkspaceTabsProps> = ({
  activeWorkspace,
  onSelectWorkspace,
  state,
  locale = "zh",
}) => {
  const isZh = locale === "zh";
  const [proOpen, setProOpen] = useState(false);
  const proRef = useRef<HTMLDivElement | null>(null);
  const isPro = activeWorkspace === "producer" || activeWorkspace === "validation_lab";

  useEffect(() => {
    if (!proOpen) return;
    const close = (event: MouseEvent) => {
      if (!proRef.current?.contains(event.target as Node)) setProOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setProOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [proOpen]);

  const choose = (id: WorkspaceId) => {
    setProOpen(false);
    onSelectWorkspace(id);
  };

  return (
    <>
      <nav className="r6-subnav" aria-label={isZh ? "产品导航" : "Product navigation"}>
        <div className="r6-subnav-inner">
          <div className="r6-nav-tabs" role="tablist" aria-label={isZh ? "比赛工作区" : "Match workspaces"}>
            {PUBLIC_TABS.map((tab) => {
              const active = activeWorkspace === tab.id;
              const badge = tab.badge(state);
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className={`r6-nav-tab ${active ? "active" : ""}`}
                  onClick={() => choose(tab.id)}
                  title={isZh ? tab.hintZh : tab.hintEn}
                >
                  <span>{isZh ? tab.zh : tab.en}</span>
                  {badge ? <b>{badge}</b> : null}
                </button>
              );
            })}
          </div>

          <div className="r6-pro-wrap" ref={proRef}>
            <button
              type="button"
              className={`r6-pro-toggle ${isPro ? "active" : ""}`}
              aria-haspopup="menu"
              aria-expanded={proOpen}
              data-testid="pro-tools-toggle"
              onClick={() => setProOpen((open) => !open)}
            >
              {isZh ? "专业工具" : "Professional tools"}
              <span aria-hidden="true">▾</span>
            </button>
            {proOpen && (
              <div className="r6-pro-menu" role="menu" aria-label={isZh ? "专业工具" : "Professional tools"}>
                {PRO_TOOLS.map((tool) => (
                  <button
                    key={tool.id}
                    type="button"
                    role="menuitem"
                    className={activeWorkspace === tool.id ? "active" : ""}
                    data-testid={`pro-tool-${tool.id}`}
                    onClick={() => choose(tool.id)}
                  >
                    <span>{isZh ? tool.zh : tool.en}</span>
                    <small>{isZh ? tool.hintZh : tool.hintEn}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </nav>

      <nav className="r6-mobile-nav" role="tablist" aria-label={isZh ? "移动端导航" : "Mobile navigation"}>
        {PUBLIC_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeWorkspace === tab.id}
            className={activeWorkspace === tab.id ? "active" : ""}
            onClick={() => choose(tab.id)}
          >
            <span>{isZh ? tab.zh : tab.en}</span>
          </button>
        ))}
        <button
          type="button"
          role="tab"
          aria-selected={isPro}
          className={isPro ? "active" : ""}
          data-testid="mobile-pro-tools"
          aria-expanded={proOpen}
          onClick={() => setProOpen((open) => !open)}
        >
          {isZh ? "专业" : "Pro"}
        </button>
        {proOpen && (
          <div className="r6-mobile-pro-menu" role="menu" aria-label={isZh ? "专业工具" : "Professional tools"}>
            {PRO_TOOLS.map((tool) => (
              <button key={tool.id} type="button" role="menuitem" onClick={() => choose(tool.id)}>
                {isZh ? tool.zh : tool.en}
              </button>
            ))}
          </div>
        )}
      </nav>
    </>
  );
};
