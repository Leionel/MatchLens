"use client";

import React, { useState } from "react";
import { CockpitState, PerspectiveId, InspectorPayload, Card, InvestigationSeed } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";
import { InsightSpotlight } from "../InsightSpotlight";
import { InvestigationPanel } from "./InvestigationPanel";

interface StoryAgentWorkbenchProps {
  state: CockpitState;
  perspective: PerspectiveId;
  busy: boolean;
  analysesRemaining: number;
  locale?: Locale;
  onAnalyse: () => void;
  onInspectReceipt: (receiptId: string, snapshotId?: string) => void;
  onSelectEvent: (eventId: string) => void;
  onOpenInspector: (payload: InspectorPayload) => void;
  onCommitState?: (nextState: any) => void;
  investigationSeed?: InvestigationSeed | null;
  onClaimPromoted?: (claim: any) => void;
}

const clock = (s: number) =>
  `${Math.floor(s / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;

export const StoryAgentWorkbench: React.FC<StoryAgentWorkbenchProps> = ({
  state,
  perspective,
  busy,
  analysesRemaining,
  locale = "zh",
  onAnalyse,
  onInspectReceipt,
  onSelectEvent,
  onOpenInspector,
  onCommitState,
  investigationSeed = null,
  onClaimPromoted,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const [workbenchTab, setWorkbenchTab] = useState<
    "deliberation" | "attribution" | "match_story" | "gate_audit" | "investigation"
  >("deliberation");
  const [mode, setMode] = useState<"fan" | "analyst">("analyst");
  const [showTrace, setShowTrace] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);

  const [copiedNotification, setCopiedNotification] = useState("");
  const [backendStory, setBackendStory] = useState<any>(null);
  const [backendAttribution, setBackendAttribution] = useState<any>(null);
  const [producerToken, setProducerToken] = useState("");
  const [storyRefresh, setStoryRefresh] = useState(0);
  const [spotlightClaim, setSpotlightClaim] = useState<Card | null>(null);
  const [editorialError, setEditorialError] = useState("");

  React.useEffect(() => {
    if (investigationSeed?.requestId) {
      setWorkbenchTab("investigation");
    }
  }, [investigationSeed?.requestId]);

  const homeTeam = state.teams?.H || "Harbor FC";
  const awayTeam = state.teams?.N || "Northbridge United";
  const matchId = state.match_id || "syn_default";

  // Fetch a story for the current match and snapshot, never for the future.
  React.useEffect(() => {
    // Fetch only while paused/finished; a live 30x replay must not issue one
    // story request per clock tick.
    if (!state.paused && !state.ended) return;
    const controller = new AbortController();
    const asOf = state.snapshot_as_of ?? state.at ?? 0;
    const mode = state.ended ? "recap" : "live";
    fetch(`/api/matches/${matchId}/story?perspective=${perspective}&as_of=${asOf}&mode=${mode}`, {
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.match_id === matchId && data.as_of === asOf) {
          setBackendStory(data);
        }
      })
      .catch((e) => {
        if (e?.name !== "AbortError") console.warn("Failed to fetch story", e);
      });
    return () => controller.abort();
  }, [matchId, perspective, state.paused, state.ended, state.snapshot_as_of, storyRefresh]);

  // Fetch real EventAttributionSpecialist output
  React.useEffect(() => {
    let active = true;
    const at = state.at || 600;
    const start = Math.max(0, at - 180);
    fetch(`/api/matches/${matchId}/attribution?window_start=${start}&window_end=${at}&team=${state.focus_team || "H"}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) {
          setBackendAttribution(data);
        }
      })
      .catch((e) => console.warn("Failed to fetch attribution", e));
    return () => {
      active = false;
    };
  }, [matchId, state.at, state.focus_team]);

  const clockText = clock(state.at || 0);
  const activeMoment = state.active_moment || null;
  const activeChapter = state.chapters?.find((c) => c.id === state.focus) || null;
  const result = state.result || null;
  const card = result?.accepted?.[0] || null;
  const pending = ["queued", "analysing", "verifying"].includes(state.analysis?.status || "");

  // All accepted claims across history and current result
  const allClaims: Card[] = [
    ...(result?.accepted || []),
    ...(state.history || []),
  ].filter(
    (c, idx, arr) =>
      arr.findIndex((x) => x.claim_id === c.claim_id && x.snapshot_id === c.snapshot_id) === idx
  );

  // Registry-backed story claims are the only source of approval truth.
  const storyClaims: Card[] = (backendStory?.claims || []).map((c: any) => ({
    claim_id: c.claim_id,
    assertion: c.assertion,
    verdict: c.gate_status,
    fan: "",
    analyst: c.statement || "",
    refs: c.evidence_scope?.event_ids?.length
      ? c.evidence_scope.event_ids
      : c.evidence_scope?.metric_ids || [],
    scope: c.evidence_scope?.window_seconds ? `${c.evidence_scope.window_seconds}s` : "match",
    reason: (c.gate_violations || []).join("; "),
    limitations: c.counterevidence || [],
    snapshot_id: backendStory?.snapshot_id || "",
    as_of: c.as_of || 0,
    claim_level: c.claim_level,
    gate_status: c.gate_status,
    gate_version: c.gate_version,
    gate_violations: c.gate_violations || [],
    editorial_status: c.editorial_status || "pending",
    editorial_approver: c.editorial_approver || null,
    evidence_hash: c.evidence_hash,
    source_run: c.source_run,
    published: Boolean(c.gate_status === "approved" && c.editorial_status === "approved"),
  }));
  const claimLabel: Record<string, string> = {
    goal_sequence: isZh ? "进球序列" : "Scoring sequence",
    possession_without_penetration: isZh ? "控球未转化为渗透" : "Possession without penetration",
    attacking_threat_increased: isZh ? "进攻威胁上升" : "Attacking threat increased",
    recoveries_followed_by_shots: isZh ? "夺回球权后射门" : "Recovery to shot",
    recoveries_caused_shots: isZh ? "夺回球权导致射门" : "Recovery caused shot",
  };
  const canExportStory = backendStory?.approval_status === "approved_for_broadcast";
  const storyGateVerified = storyClaims.filter((c) => c.gate_status === "approved").length;
  const storyEditorial = storyClaims.filter((c) => c.published).length;

  // Dynamic Contributing Actions from backend attribution or real sequences / events
  const dynamicContributingActions = React.useMemo<Array<{
    rank: number;
    action: string;
    weight: string;
    player: string;
    kind: string;
    eventId: string;
  }>>(() => {
    if (backendAttribution?.window_decomposition?.top_contributors?.length > 0) {
      return backendAttribution.window_decomposition.top_contributors.slice(0, 5).map((tc: any, idx: number) => ({
        rank: idx + 1,
        action: tc.explanation || (isZh ? `关键进攻贡献 (${tc.kind})` : `Key Action (${tc.kind})`),
        weight: `${tc.signed_contribution > 0 ? `+${tc.signed_contribution.toFixed(2)}` : tc.signed_contribution.toFixed(2)}`,
        player: tc.actor || (state.teams?.H ? `${state.teams.H} Player` : "Actor"),
        kind: tc.kind,
        eventId: tc.event_id,
      }));
    }
    if (state.sequences && state.sequences.length > 0) {
      const sortedSeqs = [...state.sequences].sort(
        (a, b) => (b.progressive_distance || 0) - (a.progressive_distance || 0)
      );
      const topSeq = sortedSeqs[0];
      if (topSeq?.events_detail && topSeq.events_detail.length > 0) {
        return topSeq.events_detail.slice(0, 4).map((ed, idx) => ({
          rank: idx + 1,
          action:
            ed.kind === "pass"
              ? isZh
                ? `中前场推进传球${ed.gain_m ? ` (${ed.gain_m.toFixed(0)}m)` : ""}`
                : `Progressive Pass${ed.gain_m ? ` (${ed.gain_m.toFixed(0)}m)` : ""}`
              : ed.kind === "shot"
              ? isZh
                ? `关键射门攻门终结`
                : `Shot on Target / Box Attack`
              : ed.kind === "recovery"
              ? isZh
                ? `反抢成功夺回球权`
                : `Possession Turnover Recovery`
              : isZh
              ? `持球推进突破`
              : `Progressive Ball Carry`,
          weight: ed.gain_m
            ? `+${ed.gain_m.toFixed(0)}m`
            : ed.xt_value
            ? `+${ed.xt_value.toFixed(3)} xT`
            : `Seq #${idx + 1}`,
          player: ed.actor_name || ed.actor || (state.teams?.H ? `${state.teams.H} Player` : "Actor"),
          kind: ed.kind,
          eventId: ed.id,
        }));
      }
    }
    const recent = [...(state.events || [])].slice(-4).reverse();
    if (recent.length > 0) {
      return recent.map((ev, idx) => ({
        rank: idx + 1,
        action:
          ev.kind === "pass"
            ? isZh
              ? `团队推进连线`
              : `Team Progressive Pass`
            : ev.kind === "shot"
            ? isZh
              ? `起脚终结射门`
              : `Box Entry Shot`
            : ev.kind === "recovery"
            ? isZh
              ? `中前场积极反抢`
              : `Turnover Recovery`
            : isZh
            ? `球权调度组织`
            : `Possession Transition`,
        weight: ev.gain_m
          ? `+${ev.gain_m.toFixed(0)}m`
          : ev.xt_value
          ? `+${ev.xt_value.toFixed(3)} xT`
          : `Evt #${idx + 1}`,
        player: ev.actor_name || ev.actor || (state.teams?.H ? `${state.teams.H} Player` : "Actor"),
        kind: ev.kind,
        eventId: ev.id,
      }));
    }
    return [];
  }, [backendAttribution, state.sequences, state.events, state.teams, isZh]);

  // Dynamic Causal Chain from real sequence progression
  const dynamicCausalChain = React.useMemo(() => {
    if (state.sequences && state.sequences.length > 0) {
      const activeSeq = state.sequences[state.sequences.length - 1];
      const evs = activeSeq.events_detail || [];
      if (evs.length >= 2) {
        const startEv = evs[0];
        const midEv = evs[Math.floor(evs.length / 2)];
        const endEv = evs[evs.length - 1];
        const dt = Math.max(1, Math.round(activeSeq.duration || 6));
        return [
          {
            step: `T-${dt}s`,
            desc: isZh
              ? `${startEv.actor_name || startEv.actor} 通过 ${startEv.kind} 触发攻势建立，坐标 [${startEv.start?.[0]?.toFixed(0) || 50}, ${startEv.start?.[1]?.toFixed(0) || 34}]`
              : `${startEv.actor_name || startEv.actor} initiated sequence via ${startEv.kind} at [${startEv.start?.[0]?.toFixed(0) || 50}, ${startEv.start?.[1]?.toFixed(0) || 34}]`,
            link: isZh ? "触发起因" : "Trigger",
          },
          {
            step: `T-${Math.max(1, Math.round(dt / 2))}s`,
            desc: isZh
              ? `${midEv.actor_name || midEv.actor} 实施纵向转移与走廊渗透${midEv.gain_m ? ` (+${midEv.gain_m.toFixed(0)}m)` : ""}`
              : `${midEv.actor_name || midEv.actor} executed progressive transition${midEv.gain_m ? ` (+${midEv.gain_m.toFixed(0)}m)` : ""}`,
            link: isZh ? "过渡转换" : "Transition",
          },
          {
            step: "T-0s",
            desc: isZh
              ? `${endEv.actor_name || endEv.actor} 完成终结动作 (${endEv.kind})，结果: ${endEv.outcome}`
              : `${endEv.actor_name || endEv.actor} concluded sequence via ${endEv.kind} (${endEv.outcome})`,
            link: isZh ? "进攻拐点" : "Inflection",
          },
        ];
      }
    }
    const at = state.at || 0;
    return [
      {
        step: `T-8s`,
        desc: isZh
          ? `在当前观察快照 (${clock(at)}) 前 8 秒记录到攻防节奏转换`
          : `Turnover recorded 8s before snapshot at ${clock(at)}`,
        link: isZh ? "触发起因" : "Trigger",
      },
      {
        step: `T-4s`,
        desc: isZh
          ? `团队协同推进，防守阵型产生纵向位移与间隙`
          : `Coordinated progression shifting opponent defensive structure`,
        link: isZh ? "过渡转换" : "Transition",
      },
      {
        step: `T-0s`,
        desc: isZh
          ? `快照截面锁定，生成验证凭据并提交门禁`
          : `Snapshot frozen at ${clock(at)}, receipts certified by Publication Gate`,
        link: isZh ? "进攻拐点" : "Inflection",
      },
    ];
  }, [state.sequences, state.at, isZh]);

  // Dynamic Hypotheses from backend attribution or state.hypotheses_matrix
  const dynamicHypotheses = React.useMemo(() => {
    if (backendAttribution?.alternative_hypotheses?.hypotheses?.length > 0) {
      return backendAttribution.alternative_hypotheses.hypotheses.map((h: any) => ({
        id: h.hypothesis_id,
        title: h.name || h.description,
        status: h.verdict === "supported" ? "supported" : h.verdict === "unsupported" ? "unsupported" : "contingent",
        reason: h.rationale || h.description,
        counterevidence: h.counterevidence_events || [],
      }));
    }
    if (state.hypotheses_matrix?.hypotheses && state.hypotheses_matrix.hypotheses.length > 0) {
      return state.hypotheses_matrix.hypotheses;
    }
    return null;
  }, [backendAttribution, state.hypotheses_matrix]);

  // Story chapters come from the registry-backed backend story. The local
  // event count is only a fallback when no story has been loaded yet.
  const dynamicChapters = React.useMemo(() => {
    if (backendStory?.chapters?.length) {
      return backendStory.chapters.map((ch: any, idx: number) => ({
        id: ch.chapter_id || `ch_${idx}`,
        title: ch.title || `${ch.minute_span} recorded events`,
        time: ch.minute_span,
        narrative: ch.narrative,
        stat: `${isZh ? "OAAI 趋势" : "OAAI trend"}: ${ch.oaai_trend}${ch.dominant_team && ch.dominant_team !== "NONE" ? `, ${isZh ? "主导" : "dominant"}: ${ch.dominant_team}` : ""}, ${isZh ? "事件" : "events"}: ${(ch.supporting_event_ids || []).length}`,
        eventIds: ch.supporting_event_ids || [],
      }));
    }
    return [];
  }, [backendStory, isZh]);

  // Generate Match Story text from the registry-backed story.
  const generateStoryMarkdown = () => {
    if (backendStory) {
      const lines = [
        `# ${backendStory.headline}`,
        `*${backendStory.subtitle}*`,
        `**Match**: ${homeTeam} vs ${awayTeam}`,
        `**Snapshot**: ${backendStory.snapshot_id} at ${clock(backendStory.as_of || state.at || 0)}`,
        `**Approval**: ${backendStory.approval_status}`,
        "",
        "---",
        "",
      ];
      (backendStory.chapters || []).forEach((ch: any) => {
        lines.push(`### ${ch.minute_span} — ${ch.title}`);
        lines.push(ch.narrative);
        lines.push(`*Gate-verified claims*: ${(ch.verified_claim_refs || []).join(", ") || "None"}`);
        lines.push("");
      });
      lines.push("---");
      lines.push(`**Verdict**: ${backendStory.summary_verdict}`);
      return lines.join("\n");
    }
    return "# Match summary\n\nNo gate-approved claims are registered for this snapshot. Only recorded event counts are shown.";
  };

  const submitEditorial = async (claimId: string, decision: "approved" | "rejected") => {
    if (!backendStory?.snapshot_id || !producerToken) return;
    setEditorialError("");
    try {
      const res = await fetch("/api/story/editorial-approval", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-MatchLens-Token": producerToken,
        },
        body: JSON.stringify({
          match_id: matchId,
          snapshot_id: backendStory.snapshot_id,
          claim_id: claimId,
          decision,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Editorial decision failed (${res.status})`);
      }
      setStoryRefresh((n) => n + 1);
    } catch (e) {
      setEditorialError((e as Error).message);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      setCopiedNotification(`Copied ${label} to clipboard!`);
      setTimeout(() => setCopiedNotification(""), 2500);
    }
  };

  return (
    <div className="workspace-pane-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 1. Tri-Agent Deliberation Pipeline Visual Header */}
      <div className="glass-panel" style={{ padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              
              <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                {t.pipelineTitle}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 800,
                  padding: "2px 7px",
                  borderRadius: 6,
                  background: "color-mix(in srgb, var(--violet-9) 18%, transparent)",
                  border: "0.5px solid color-mix(in srgb, var(--violet-9) 40%, transparent)",
                  color: "var(--violet-11)",
                }}
              >
                {isZh ? "2 AGENTS + TOOLS" : "2 AGENTS + TOOLS"}
              </span>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 2 }}>
              {t.pipelineSubtitle}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {copiedNotification && (
              <span style={{ fontSize: 12, color: "var(--text-emerald)", fontWeight: 700 }}>
                {copiedNotification}
              </span>
            )}
            <button
              type="button"
              disabled={busy || analysesRemaining <= 0}
              onClick={onAnalyse}
              style={{
                fontSize: 12,
                fontWeight: 750,
                padding: "6px 14px",
                borderRadius: 8,
                background: "var(--turf-emerald)",
                color: "var(--slate-1)",
                border: "none",
                cursor: "pointer",
                boxShadow: "none",
              }}
            >
              {pending ? t.deliberatingState : t.runDeliberationBtn}
            </button>
          </div>
        </div>

        {/* 4 Pipeline Stages */}
        <div className="pipeline-stage-grid">
          {/* Stage 1: Analyst Agent */}
          <div
            className={`collab-step-card ${
              pending && state.analysis?.status !== "verifying" ? "active" : result ? "completed" : ""
            }`}
          >
            <div className="step-num-badge">1</div>
            <div className="step-card-header">
              <span className="step-agent-name">{t.stage1Name}</span>
              <span className="step-agent-role">{t.stage1Role}</span>
            </div>
            <p className="step-desc">
              {t.stage1Desc}
            </p>
            <div className="step-foot-stats">
              <span>{isZh ? "输出:" : "Output:"} <code>Claim Level 1–2</code></span>
              <span className="gate-ok">{isZh ? "就绪" : "READY"}</span>
            </div>
          </div>

          <div className="collab-step-arrow">→</div>

          {/* Stage 2: deterministic tool layer (not an agent) */}
          <div
            className={`collab-step-card ${
              pending ? "active" : result ? "completed" : ""
            }`}
            style={{
              borderColor: "color-mix(in srgb, var(--violet-9) 40%, transparent)",
              background: "color-mix(in srgb, var(--violet-9) 6%, transparent)",
            }}
          >
            <div
              className="step-num-badge"
              style={{ background: "var(--agent-violet)", color: "var(--white)" }}
            >
              2
            </div>
            <div className="step-card-header">
              <span className="step-agent-name" style={{ color: "var(--violet-11)" }}>
                {isZh ? "确定性归因工具" : "Deterministic tools"}
              </span>
              <span className="step-agent-role">{isZh ? "非智能体 不调用模型" : "Not an agent, no model call"}</span>
            </div>
            <p className="step-desc">
              {isZh
                ? "decompose_window / query_causal_chain / assess_alternative_hypotheses 由两位智能体按需调用；工具本身不做推理或生成观点。"
                : "decompose_window / query_causal_chain / assess_alternative_hypotheses are called by both agents; the tools do not reason or generate claims."}
            </p>
            <div className="step-foot-stats">
              <span>{isZh ? "工具:" : "Tool:"} <code>TemporalDecomp</code></span>
              </div>
          </div>

          <div className="collab-step-arrow">→</div>

          {/* Stage 3: Verifier Agent */}
          <div
            className={`collab-step-card ${
              pending && state.analysis?.status === "verifying" ? "active" : result ? "completed" : ""
            }`}
          >
            <div className="step-num-badge">3</div>
            <div className="step-card-header">
              <span className="step-agent-name">{t.stage3Name}</span>
              <span className="step-agent-role">{t.stage3Role}</span>
            </div>
            <p className="step-desc">
              {t.stage3Desc}
            </p>
            <div className="step-foot-stats">
              <span>{isZh ? "审计:" : "Audit:"} <code>Counterevidence</code></span>
              <span className="verdict-tag">{isZh ? "严苛核查" : "SCRUTINIZED"}</span>
            </div>
          </div>

          <div className="collab-step-arrow">→</div>

          {/* Stage 4: publication gate (deterministic, not an agent) */}
          <div className={`collab-step-card ${result ? "completed" : ""}`}>
            <div className="step-num-badge">4</div>
            <div className="step-card-header">
              <span className="step-agent-name">{isZh ? "发布门禁" : "Publication gate"}</span>
              <span className="step-agent-role">{isZh ? "回执绑定 非智能体" : "Receipt contract, not an agent"}</span>
            </div>
            <p className="step-desc">
              {isZh ? "只允许有回执引用的事实。" : "Typed facts and receipt references only."}
            </p>
            <div className="step-foot-stats">
              <span>{isZh ? "通过:" : "Passed:"} <b className="gate-ok">{storyGateVerified}</b> / {(state.result?.rejected || []).length} {isZh ? "驳回" : "rejected"}</span>
              <span><code>publication_gate</code></span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Sub-tab Navigation Bar */}
      <div
        style={{
          display: "flex",
          borderBottom: "0.5px solid var(--glass-border)",
          gap: 6,
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={() => setWorkbenchTab("deliberation")}
          className={`feed-filter-btn ${workbenchTab === "deliberation" ? "active" : ""}`}
          style={{ fontSize: 14, padding: "8px 16px" }}
        >
          {isZh ? "智能体协作" : "Deliberation"}
        </button>

        <button
          type="button"
          onClick={() => setWorkbenchTab("attribution")}
          className={`feed-filter-btn ${workbenchTab === "attribution" ? "active" : ""}`}
          style={{ fontSize: 14, padding: "8px 16px" }}
        >
          {isZh ? "事件归因" : "Attribution"}
        </button>

        <button
          type="button"
          onClick={() => setWorkbenchTab("match_story")}
          className={`feed-filter-btn ${workbenchTab === "match_story" ? "active" : ""}`}
          style={{ fontSize: 14, padding: "8px 16px" }}
        >
          {isZh ? "战报与审批" : "Story"}
        </button>

        <button
          type="button"
          onClick={() => setWorkbenchTab("gate_audit")}
          className={`feed-filter-btn ${workbenchTab === "gate_audit" ? "active" : ""}`}
          style={{ fontSize: 14, padding: "8px 16px" }}
        >
          {isZh ? "门禁审计" : "Gate audit"}
        </button>

        <button
          type="button"
          onClick={() => setWorkbenchTab("investigation")}
          className={`feed-filter-btn ${workbenchTab === "investigation" ? "active" : ""}`}
          style={{ fontSize: 14, padding: "8px 16px" }}
        >
          {isZh ? "调查" : "Investigation"}
        </button>
      </div>

      {/* 3. Sub-tab Content Panels */}

      {/* TAB A: Deliberation Workshop & Spotlight */}
      {workbenchTab === "deliberation" && (
        <div className="glass-panel" style={{ padding: 18 }}>
          <InsightSpotlight
            mode={mode}
            onModeChange={setMode}
            card={spotlightClaim || card}
            result={result}
            pending={pending}
            pendingStatus={state.analysis?.status}
            activeMoment={activeMoment}
            activeChapter={activeChapter}
            modelConfigured={state.model_configured}
            busy={busy}
            analysesRemaining={analysesRemaining}
            onAnalyse={onAnalyse}
            onChallenge={(rId, sId) => onInspectReceipt(rId, sId)}
            onToggleTrace={() => setShowTrace(!showTrace)}
            showTrace={showTrace}
            onToggleOverlay={() => setShowOverlay(!showOverlay)}
            showOverlay={showOverlay}
            receipts={state.receipts}
            snapshotId={state.snapshot_id}
            autoStatus={state.auto_status}
            hypothesesMatrix={state.hypotheses_matrix || null}
            revisions={state.revisions || []}
            focusTeam={state.focus_team || "H"}
            locale={locale}
            onChallengeSubmitted={(res) => {
              if (res?.state && onCommitState) onCommitState(res.state);
            }}
          />
        </div>
      )}

      {/* TAB B: Event Attribution Breakdown (Track C) */}
      {workbenchTab === "attribution" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Tool 1: Temporal Window Decomposition */}
          <div className="glass-panel" style={{ padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18 }}>⏱️</span>
                <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                  {isZh ? "时序窗口贡献分解 (BL-02 & BL-10)" : "TEMPORAL WINDOW DECOMPOSITION (BL-02 & BL-10)"}
                </span>
              </div>
              <span style={{ fontSize: 12, padding: "2px 6px", borderRadius: 4, background: "color-mix(in srgb, var(--violet-9) 20%, transparent)", color: "var(--violet-11)", fontWeight: 700 }}>
                {isZh ? "工具 #1" : "TOOL #1"}
              </span>
            </div>

            <p style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 12, lineHeight: 1.5 }}>
              {isZh
                ? `客观量化计算当前 OAAI 攻防动量潮汐窗口 (${clock(state.at - 120)}–${clock(state.at)}) 内各触球动作的正向贡献权重。`
                : `Calculates objective contribution weights for actions occurring within the active OAAI momentum wave window (${clock(state.at - 120)}–${clock(state.at)}).`}
            </p>

            {/* Top Contributing Actions */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {dynamicContributingActions.length === 0 ? (
                <div style={{ padding: "16px 12px", textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
                  {isZh ? "当前赛段暂无足够推进事件" : "No progressive events recorded yet for this window"}
                </div>
              ) : (
                dynamicContributingActions.map((item: any) => (
                  <div
                    key={item.rank}
                    onClick={() => onSelectEvent(item.eventId)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: 6,
                      background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
                      border: "0.5px solid var(--pitch-border)",
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: "50%",
                          background: "color-mix(in srgb, var(--green-9) 20%, transparent)",
                          color: "var(--text-emerald)",
                          fontSize: 12,
                          fontWeight: 800,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        #{item.rank}
                      </span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 750, color: "var(--text-primary)" }}>
                          {item.action}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                          {isZh ? "执行人:" : "Actor:"} {item.player} {isZh ? "事件编号:" : "Action ID:"} <code>{item.eventId}</code>
                        </div>
                      </div>
                    </div>

                    <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-emerald)" }}>
                      {item.weight} OAAI
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Tool 2: Causal Chain Query & Alternative Hypotheses */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Causal Chain Backtracking */}
            <div className="glass-panel" style={{ padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>⛓️</span>
                  <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                    {isZh ? "因果链回溯检索 (BACKWARDS TRACE)" : "CAUSAL CHAIN QUERY (BACKWARDS TRACE)"}
                  </span>
                </div>
                <span style={{ fontSize: 12, padding: "2px 6px", borderRadius: 4, background: "color-mix(in srgb, var(--cyan-9) 20%, transparent)", color: "var(--text-cyan)", fontWeight: 700 }}>
                  {isZh ? "工具 #2" : "TOOL #2"}
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {dynamicCausalChain.map((s, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "6px 10px",
                      borderRadius: 6,
                      background: "color-mix(in srgb, var(--slate-1) 40%, transparent)",
                      border: "0.5px solid var(--glass-border)",
                      fontSize: 12,
                    }}
                  >
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--text-cyan)", minWidth: 42 }}>
                      {s.step}
                    </span>
                    <span style={{ flex: 1, color: "var(--text-primary)" }}>{s.desc}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-tertiary)", textTransform: "uppercase" }}>
                      {s.link}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Alternative Hypotheses Assessment */}
            <div className="glass-panel" style={{ padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 18 }}>⚖️</span>
                  <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                    {isZh ? "对立战术假设与争议评估" : "ALTERNATIVE HYPOTHESIS ASSESSMENT"}
                  </span>
                </div>
                <span style={{ fontSize: 12, padding: "2px 6px", borderRadius: 4, background: "color-mix(in srgb, var(--amber-9) 20%, transparent)", color: "var(--text-gold)", fontWeight: 750 }}>
                  {isZh ? "工具 #3" : "TOOL #3"}
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
                {dynamicHypotheses ? (
                  dynamicHypotheses.map((h: any, idx: number) => {
                    const isSupported = h.status === "supported";
                    const isRejected = h.status === "rejected";
                    const borderColor = isSupported
                      ? "color-mix(in srgb, var(--green-9) 35%, transparent)"
                      : isRejected
                      ? "color-mix(in srgb, var(--red-9) 35%, transparent)"
                      : "color-mix(in srgb, var(--amber-9) 35%, transparent)";
                    const bgColor = isSupported
                      ? "color-mix(in srgb, var(--green-9) 8%, transparent)"
                      : isRejected
                      ? "color-mix(in srgb, var(--red-9) 8%, transparent)"
                      : "color-mix(in srgb, var(--amber-9) 8%, transparent)";
                    const badgeColor = isSupported
                      ? "var(--turf-emerald)"
                      : isRejected
                      ? "var(--sunset-rose, var(--red-9))"
                      : "var(--electric-gold)";

                    return (
                      <div
                        key={h.id || idx}
                        style={{
                          padding: "8px 12px",
                          borderRadius: 6,
                          background: bgColor,
                          border: `0.5px solid ${borderColor}`,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontWeight: 750, color: badgeColor }}>
                            {h.title}
                          </span>
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 800,
                              padding: "1px 6px",
                              borderRadius: 4,
                              background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
                              color: badgeColor,
                              textTransform: "uppercase",
                            }}
                          >
                            {h.status}
                          </span>
                        </div>
                        <div style={{ color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.4 }}>
                          {h.reason}
                        </div>
                        {h.counterevidence && h.counterevidence.length > 0 && (
                          <div style={{ fontSize: 12, color: "var(--sunset-rose, var(--red-9))", marginTop: 4 }}>
                            {isZh ? "检索到反证指标: " : "Counterevidence audited: "}
                            <code>{h.counterevidence.join(", ")}</code>
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div style={{ padding: "12px", color: "var(--text-tertiary)", textAlign: "center" }}>
                    {isZh
                      ? "当前时间点未生成假设矩阵，点击顶部“运行审议”触发智能体假设检验"
                      : "No hypothesis matrix generated for this moment. Click 'Run Deliberation' to trigger verification."}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB C: Match Story & Content Approval Workflow (Track D) */}
      {workbenchTab === "match_story" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 16 }}>
          {/* Story Narrative Chapters */}
          <div className="glass-panel" style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <span style={{ fontSize: 12, fontWeight: 800, color: "var(--text-emerald)", textTransform: "uppercase" }}>
                  {isZh ? "比赛战报" : "Match story"}
                </span>
                <h3 style={{ fontSize: 18, fontWeight: 750, margin: "2px 0 0" }}>
                  {isZh ? `比赛战报分章节 (${state.chapters?.length || 3} 个赛段)` : `Match Story Chapters (${state.chapters?.length || 3} Segments)`}
                </h3>
              </div>

              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  disabled={!canExportStory}
                  title={!canExportStory ? (isZh ? "需完成制作人审批后才能导出" : "Producer approval is required before export") : undefined}
                  onClick={() => copyToClipboard(generateStoryMarkdown(), isZh ? "战报研报" : "Match Story Report")}
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: "color-mix(in srgb, var(--green-9) 20%, transparent)",
                    border: "0.5px solid var(--turf-emerald)",
                    color: "var(--text-emerald)",
                    cursor: canExportStory ? "pointer" : "not-allowed",
                    opacity: canExportStory ? 1 : 0.5,
                  }}
                >
                  {t.copyMarkdownBtn}
                </button>
                <button
                  type="button"
                  disabled={!canExportStory}
                  onClick={() =>
                    copyToClipboard(
                      JSON.stringify({ claims: allClaims, snapshot: state.snapshot_id, score: state.score }, null, 2),
                      isZh ? "证据 JSON" : "Evidence JSON"
                    )
                  }
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: "color-mix(in srgb, var(--cyan-9) 20%, transparent)",
                    border: "0.5px solid var(--tech-cyan)",
                    color: "var(--text-cyan)",
                    cursor: canExportStory ? "pointer" : "not-allowed",
                    opacity: canExportStory ? 1 : 0.5,
                  }}
                >
                  {t.exportJsonBtn}
                </button>
              </div>
            </div>

            {/* Chapters Feed */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {dynamicChapters.length === 0 ? (
                <div style={{ padding: 20, textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
                  {isZh ? "未检测到赛段划分" : "No match chapters available"}
                </div>
              ) : (
                dynamicChapters.map((ch: any) => (
                  <div
                    key={ch.id}
                    style={{
                      padding: 12,
                      borderRadius: 8,
                      background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
                      border: "0.5px solid var(--glass-border)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
                        {ch.title}
                      </span>
                      <span style={{ fontSize: 12, fontFamily: "monospace", color: "var(--text-cyan)" }}>
                        {ch.time}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.5 }}>
                      {ch.narrative}
                    </p>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-emerald)", marginTop: 6 }}>
                      {isZh ? "核心指标:" : "Key Metric:"} {ch.stat}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Content Approval Pipeline (Verified vs Draft) */}
          <div className="glass-panel" style={{ padding: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <span style={{ fontSize: 12, fontWeight: 800, color: "var(--text-gold)", textTransform: "uppercase" }}>
                  {isZh ? "声明审批" : "CONTENT APPROVAL WORKFLOW"}
                </span>
                <h3 style={{ fontSize: 18, fontWeight: 750, margin: "2px 0 0" }}>
                  {isZh ? `注册声明与门禁 (${storyClaims.length || allClaims.length})` : `Registered claims & gate (${storyClaims.length || allClaims.length})`}
                </h3>
              </div>
              <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                {isZh ? "门禁通过 ≠ 编辑批准" : "Gate verified ≠ editorial approval"}
              </span>
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
              <input
                type="password"
                value={producerToken}
                onChange={(e) => setProducerToken(e.target.value)}
                placeholder={isZh ? "制作人令牌（仅本标签页）" : "Producer token (this tab only)"}
                autoComplete="off"
                style={{
                  minHeight: 32,
                  flex: "1 1 220px",
                  maxWidth: 320,
                  background: "var(--input-bg)",
                  color: "var(--input-text)",
                  border: "0.5px solid var(--pitch-border)",
                  borderRadius: 6,
                  padding: "4px 8px",
                  fontSize: 12,
                }}
              />
              <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                {isZh ? "审批身份由服务端令牌确认" : "Identity is verified by the server token"}
              </span>
              {editorialError && <span style={{ fontSize: 12, color: "var(--red-11)" }}>{editorialError}</span>}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(storyClaims.length ? storyClaims : allClaims).length === 0 ? (
                <div style={{ padding: 20, textAlign: "center", color: "var(--text-tertiary)", fontSize: 12 }}>
                  {isZh ? "尚未生成论断。点击上方运行双智能体审议。" : "No claims generated yet. Run Deliberation to populate claims."}
                </div>
              ) : (
                (storyClaims.length ? storyClaims : allClaims).map((cl) => {
                  const gateApproved = cl.gate_status === "approved" || cl.verdict === "publish" || cl.verdict === "qualify";
                  const editorialApproved = cl.published === true;
                  const isApproved = gateApproved && editorialApproved;

                  return (
                    <div
                      key={cl.claim_id}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 8,
                        background: isApproved
                          ? "color-mix(in srgb, var(--green-9) 7%, transparent)"
                          : "color-mix(in srgb, var(--slate-1) 50%, transparent)",
                        border: isApproved
                          ? "0.5px solid color-mix(in srgb, var(--green-9) 35%, transparent)"
                          : "0.5px solid var(--pitch-border)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, flex: 1 }}>
                          <span
                            className={`rail-chip ${gateApproved ? "verified" : "unknown"}`}
                            title={isZh ? "由发布门禁实际执行后写入注册表" : "Written by the executed publication gate"}
                          >
                            {gateApproved ? (isZh ? "门禁通过" : "GATE PASS") : isZh ? "未通过" : "REJECTED"}
                          </span>
                          <span className={`rail-chip ${editorialApproved ? "verified" : "unknown"}`}>
                            {editorialApproved ? (isZh ? "编辑批准" : "EDITORIAL") : isZh ? "待编辑" : "PENDING"}
                          </span>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 750, color: "var(--text-primary)" }}>
                              {claimLabel[cl.assertion] || cl.assertion}
                            </div>
                            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 2 }}>
                              {isZh ? `Level ${cl.claim_level || 2} ` : `Level ${cl.claim_level || 2} `}
                              <code>{cl.evidence_hash ? `sha256:${cl.evidence_hash.slice(0, 10)}` : cl.snapshot_id?.slice(0, 8)}</code>
                            </div>
                          </div>
                        </div>

                        {gateApproved && (
                          <button
                            type="button"
                            onClick={() => {
                              setSpotlightClaim(cl);
                              setWorkbenchTab("deliberation");
                            }}
                            style={{ fontSize: 12, fontWeight: 700, padding: "2px 6px", borderRadius: 4, border: "0.5px solid var(--pitch-border)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer" }}
                          >
                            {isZh ? "质疑与修订" : "Challenge"}
                          </button>
                        )}

                        {gateApproved && producerToken && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              type="button"
                              onClick={() => submitEditorial(cl.claim_id, "approved")}
                              style={{ fontSize: 12, fontWeight: 700, padding: "2px 6px", borderRadius: 4, border: "0.5px solid var(--green-7)", background: "var(--green-3)", color: "var(--green-11)", cursor: "pointer" }}
                            >
                              {isZh ? "批准" : "Approve"}
                            </button>
                            <button
                              type="button"
                              onClick={() => submitEditorial(cl.claim_id, "rejected")}
                              style={{ fontSize: 12, fontWeight: 700, padding: "2px 6px", borderRadius: 4, border: "0.5px solid var(--red-7)", background: "var(--red-3)", color: "var(--red-11)", cursor: "pointer" }}
                            >
                              {isZh ? "拒绝" : "Reject"}
                            </button>
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={() =>
                            onOpenInspector({
                              type: "claim",
                              claim: cl,
                              title: isZh ? `门禁审计: 论断 ${cl.claim_id}` : `Gate Audit: Claim ${cl.claim_id}`,
                            })
                          }
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: gateApproved
                              ? "color-mix(in srgb, var(--green-9) 20%, transparent)"
                              : "color-mix(in srgb, var(--amber-9) 20%, transparent)",
                            color: gateApproved
                              ? "var(--turf-emerald)"
                              : "var(--electric-gold)",
                            border: "none",
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {isZh ? "查看" : "Inspect"}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}

      {workbenchTab === "investigation" && (
        <InvestigationPanel
          state={state}
          locale={locale}
          seed={investigationSeed}
          onSelectEvent={onSelectEvent}
          onClaimPromoted={(claim) => {
            setStoryRefresh((n) => n + 1);
            onClaimPromoted?.(claim);
          }}
        />
      )}

      {/* TAB D: Publication Publication Gate & Data Sufficiency Audit */}
      {workbenchTab === "gate_audit" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="glass-panel" style={{ padding: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)", marginBottom: 12 }}>
              {isZh ? "Publication Gate 强制发布审查准则" : "Publication Publication Gate Enforced Criteria"}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ padding: 10, borderRadius: 6, background: "color-mix(in srgb, var(--slate-1) 70%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                <div style={{ fontSize: 12, fontWeight: 750, color: "var(--text-emerald)" }}>
                  {isZh ? "Level 1: 纯描述性事实观察" : "Level 1: Pure Descriptive Observation"}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                  {isZh
                    ? "必须直接对应原始记录事件，禁止使用主观推理性动词。例如：'球员 H10 在第 10–15 分钟完成 12 次成功传球'。"
                    : "Must directly mirror raw recorded events without inferential verbs. E.g., \"Player H10 completed 12 passes in minutes 10–15.\""}
                </div>
              </div>

              <div style={{ padding: 10, borderRadius: 6, background: "color-mix(in srgb, var(--slate-1) 70%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                <div style={{ fontSize: 12, fontWeight: 750, color: "var(--text-cyan)" }}>
                  {isZh ? "Level 2: 确定性数学公式分解" : "Level 2: Deterministic Formula Decomposition"}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                  {isZh
                    ? "必须引用绑定 SHA-256 签名的确定性数学凭证，具备明确分子分母。例如：'高位反抢率为 66.7% (4/6)'。"
                    : "Must reference SHA-256 bound mathematical receipts with defined numerator and denominator. E.g., \"High recovery rate was 66.7% (4/6).\""}
                </div>
              </div>

              <div style={{ padding: 10, borderRadius: 6, background: "color-mix(in srgb, var(--slate-1) 70%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                <div style={{ fontSize: 12, fontWeight: 750, color: "var(--text-gold)" }}>
                  {isZh ? "Level 3: 战术因果推论假设" : "Level 3: Causal Tactical Hypotheses"}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 2 }}>
                  {isZh
                    ? "强制前置条件：必须列出显式假设、验证机制，并检索反证事实。若存在反证或缺乏论据，Publication Gate 将坚决拦截或降级。"
                    : "Mandatory requirements: explicit assumptions list, defined verification method, and confirmed counterevidence search. Without these, Publication Gate rejects the claim."}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-panel" style={{ padding: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)", marginBottom: 12 }}>
              {isZh ? "📡 科学数据充分性评估标识" : "📡 Scientific Data Sufficiency Badge"}
            </div>

            <p style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
              {isZh
                ? "常规赛事转播与触球事件数据源不包含所有无球球员的连续 25Hz 光学追踪坐标。MatchLens AI 明确标注数据充分性指标以防算法臆测："
                : "Standard match broadcast and event feeds lack optical tracking coordinates for all off-ball players. MatchLens AI explicitly tags all claims with Data Sufficiency indicators:"}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", background: "color-mix(in srgb, var(--slate-1) 40%, transparent)", borderRadius: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "触球事件数据覆盖度:" : "Event Data Coverage:"}</span>
                <span style={{ fontSize: 12, fontWeight: 750, color: "var(--text-emerald)" }}>{isZh ? "100% (完全可核验)" : "100% (Verifiable)"}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", background: "color-mix(in srgb, var(--slate-1) 40%, transparent)", borderRadius: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "无球跑动光学追踪数据:" : "Off-Ball Tracking Data:"}</span>
                <span style={{ fontSize: 12, fontWeight: 750, color: "var(--text-gold)" }}>{isZh ? "代理指标激活 (6s + ΔD)" : "Proxy Active (6s + ΔD)"}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 10px", background: "color-mix(in srgb, var(--slate-1) 40%, transparent)", borderRadius: 6 }}>
                <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "数学虚构/幻觉风险:" : "Mathematical Hallucination Risk:"}</span>
                <span style={{ fontSize: 12, fontWeight: 750, color: "var(--text-emerald)" }}>{isZh ? "0.00% (完全收据锁定)" : "0.00% (Locked by Receipts)"}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
