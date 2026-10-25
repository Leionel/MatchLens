"use client";

import React from "react";
import { CockpitState, WorkspaceId } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";

interface WorkspaceTabsProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (id: WorkspaceId) => void;
  state: CockpitState;
  locale?: Locale;
}

export const WorkspaceTabs: React.FC<WorkspaceTabsProps> = ({
  activeWorkspace,
  onSelectWorkspace,
  state,
  locale = "zh",
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";

  // The public provider state is a bounded replay window; the coverage total
  // is the observed event count the match actually has.
  const eventCount = state.coverage?.event_count ?? state.events?.length ?? 0;
  const sequenceCount = state.sequences?.length || 0;
  const claimsCount = (state.result?.accepted?.length || 0) + (state.history?.length || 0);

  const tabs: { id: WorkspaceId; index: string; label: string; countBadge: string }[] = [
    {
      id: "match_hub",
      index: "00",
      label: isZh ? "比赛库" : "Match Library",
      countBadge: isZh ? "赛事" : "Browse",
    },
    {
      id: "match_center",
      index: "01",
      label: t.workspaceMatchCenter,
      countBadge: `${state.score.H}–${state.score.N} ${eventCount}`,
    },
    {
      id: "tactical_lab",
      index: "02",
      label: t.workspaceTacticalLab,
      countBadge: `${sequenceCount} ${isZh ? "序列" : "seq"}`,
    },
    {
      id: "story_agent",
      index: "03",
      label: t.workspaceStoryAgent,
      countBadge: isZh ? "注册表" : "Registry",
    },
    {
      id: "producer",
      index: "04",
      label: isZh ? "制作人" : "Producer",
      countBadge: isZh ? "发布" : "Publish",
    },
    {
      id: "validation_lab",
      index: "05",
      label: t.workspaceValidationLab,
      countBadge: "xT",
    },
  ];

  return (
    <nav className="workspace-tabs-bar" aria-label="Cockpit Workspaces">
      <div className="workspace-tabs-container" role="tablist">
        {tabs.map((tab) => {
          const isActive = activeWorkspace === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`workspace-tab-item ${isActive ? "active" : ""}`}
              onClick={() => onSelectWorkspace(tab.id)}
              aria-selected={isActive}
              role="tab"
            >
              <span className="workspace-tab-index">{tab.index}</span>
              <span className="workspace-tab-label">{tab.label}</span>
              <span className="workspace-tab-badge">{tab.countBadge}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
