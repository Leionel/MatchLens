"use client";

import React from "react";
import { CockpitState, WorkspaceId } from "./types";

interface WorkspaceTabsProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (id: WorkspaceId) => void;
  state: CockpitState;
}

export const WorkspaceTabs: React.FC<WorkspaceTabsProps> = ({
  activeWorkspace,
  onSelectWorkspace,
  state,
}) => {
  const eventCount = state.events?.length || 0;
  const sequenceCount = state.sequences?.length || 0;
  const claimsCount = state.result?.accepted?.length || (state.history?.length || 0);

  const tabs: { id: WorkspaceId; label: string; icon: string; countBadge: string | number }[] = [
    {
      id: "match_center",
      label: "Match Center (比赛中心)",
      icon: "🏟️",
      countBadge: `${state.score.H}-${state.score.N} (${eventCount})`,
    },
    {
      id: "tactical_lab",
      label: "Tactical Lab (战术与空间实验室)",
      icon: "🧭",
      countBadge: `${sequenceCount} S2`,
    },
    {
      id: "story_agent",
      label: "Story & Agent Workbench (研报智能体)",
      icon: "🤖",
      countBadge: `${claimsCount} Gate`,
    },
    {
      id: "validation_lab",
      label: "Validation Lab (科研与模型审计)",
      icon: "📊",
      countBadge: "xT & A/B/C",
    },
  ];

  return (
    <nav className="workspace-tabs-bar" aria-label="Cockpit Workspaces">
      <div className="workspace-tabs-container">
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
              <span style={{ fontSize: 16 }}>{tab.icon}</span>
              <span>{tab.label}</span>
              <span className="workspace-tab-badge">{tab.countBadge}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
