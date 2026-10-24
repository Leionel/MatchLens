"use client";

import React from "react";
import { CockpitState } from "./types";
import { Locale } from "../../lib/i18n";

interface InvestigationPanelProps {
  state: CockpitState;
  locale?: Locale;
}

type Plan = {
  investigation_id: string;
  match_id: string;
  snapshot_id: string;
  as_of: number;
  execution_mode: string;
  agent_status: string;
  dataset_revision?: string | null;
  tool_receipts: { sequence: number; tool: string; status: string; summary: string; result_sha256?: string }[];
  findings: { finding_id: string; level: number; statement: string; event_ids: string[]; metric_ids: string[]; limitations: string[] }[];
  explanations: { explanation_id: string; hypothesis: string; status: string; supporting_evidence: string[]; counterevidence: string[]; verification: string; limitations: string[] }[];
  gate_preview: { assertion: string; refs: string[]; status: string; violations: string[]; statement: string; persisted: boolean };
  not_inferable: string[];
  unresolved: string[];
};

const statusTone: Record<string, string> = {
  supported: "var(--text-emerald)",
  qualified: "var(--text-gold)",
  rejected: "var(--red-11)",
  insufficient_evidence: "var(--text-tertiary)",
  approved: "var(--text-emerald)",
  disputed: "var(--text-gold)",
  not_formed: "var(--text-tertiary)",
};

export const InvestigationPanel: React.FC<InvestigationPanelProps> = ({ state, locale = "zh" }) => {
  const isZh = locale === "zh";
  const [question, setQuestion] = React.useState("");
  const [focusType, setFocusType] = React.useState<"moment" | "event" | "metric" | "sequence">("moment");
  const [focusId, setFocusId] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [plan, setPlan] = React.useState<Plan | null>(null);

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          match_id: state.match_id,
          at: state.snapshot_as_of ?? state.at,
          team: state.focus_team || "H",
          focus_type: focusType,
          focus_id: focusId || null,
          question,
        }),
      });
      if (!res.ok) throw new Error(`Investigation failed (${res.status})`);
      const data: Plan = await res.json();
      if (data.match_id !== state.match_id || data.as_of !== (state.snapshot_as_of ?? state.at)) {
        throw new Error("Stale investigation response");
      }
      setPlan(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: 16, display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 700 }}>{isZh ? "调查工作台" : "Investigation"}</h3>
          <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
            {isZh ? "确定性工具执行；不会自动生成未经验证的观点。" : "Deterministic tools only; no unverified narrative is published."}
          </p>
        </div>
        <span className="rail-chip neutral" title={plan?.dataset_revision || undefined}>
          {plan ? `${plan.agent_status === "not_run" ? (isZh ? "Agent 未运行" : "Agent not run") : plan.agent_status} / ${plan.execution_mode}` : isZh ? "待运行" : "Idle"}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "调查焦点" : "Focus"}
          <select
            value={focusType}
            onChange={(e) => setFocusType(e.target.value as typeof focusType)}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          >
            <option value="moment">{isZh ? "当前异常/时刻" : "Current moment"}</option>
            <option value="event">{isZh ? "事件 ID" : "Event ID"}</option>
            <option value="metric">{isZh ? "指标" : "Metric"}</option>
            <option value="sequence">{isZh ? "控球序列" : "Sequence"}</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)" }}>
          {isZh ? "焦点 ID（可选）" : "Focus ID (optional)"}
          <input
            value={focusId}
            onChange={(e) => setFocusId(e.target.value)}
            placeholder="E0001 / SEQ-001 / shots"
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)", gridColumn: "span 2" }}>
          {isZh ? "问题" : "Question"}
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={isZh ? "这段攻势由什么造成？" : "What produced this attacking spell?"}
            style={{ minHeight: 34, background: "var(--input-bg)", color: "var(--input-text)", border: "0.5px solid var(--pitch-border)", borderRadius: 6, padding: "4px 8px" }}
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button type="button" onClick={run} disabled={busy || !state.match_id} style={{ minHeight: 34, fontSize: 12, fontWeight: 700 }}>
          {busy ? (isZh ? "执行中..." : "Running...") : isZh ? "运行调查" : "Run investigation"}
        </button>
        {error && <span style={{ color: "var(--red-11)", fontSize: 12 }}>{error}</span>}
      </div>

      {plan && (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {isZh ? "快照" : "Snapshot"} <code>{plan.snapshot_id.slice(0, 18)}</code> / {plan.as_of}s / {plan.tool_receipts.length} {isZh ? "次工具调用" : "tool calls"}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "工具回执" : "Tool receipts"}</div>
            {plan.tool_receipts.map((step) => (
              <div key={step.sequence} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 12, color: "var(--text-secondary)" }}>
                <code>{step.sequence.toString().padStart(2, "0")}</code>
                <b style={{ color: "var(--text-primary)" }}>{step.tool}</b>
                <span>{step.status}</span>
                <span style={{ color: "var(--text-tertiary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{step.summary}</span>
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "已记录发现" : "Findings"}</div>
            {plan.findings.map((finding) => (
              <div key={finding.finding_id} style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                <b style={{ color: "var(--text-primary)" }}>L{finding.level}</b> {finding.statement}
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "候选解释" : "Candidate explanations"}</div>
            {plan.explanations.map((item) => (
              <div key={item.explanation_id} style={{ borderTop: "0.5px solid var(--pitch-border)", paddingTop: 8, display: "grid", gap: 4 }}>
                <div style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, fontWeight: 700 }}>{item.hypothesis}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: statusTone[item.status] || "var(--text-secondary)" }}>{item.status}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{item.verification}</div>
                {item.supporting_evidence.length > 0 && <div style={{ fontSize: 12, color: "var(--text-emerald)" }}>+ {item.supporting_evidence.join(", ")}</div>}
                {item.counterevidence.length > 0 && <div style={{ fontSize: 12, color: "var(--red-11)" }}>− {item.counterevidence.join(", ")}</div>}
              </div>
            ))}
          </div>

          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "门禁预览（未持久化）" : "Gate preview (not persisted)"}</div>
            <div style={{ fontSize: 12, color: statusTone[plan.gate_preview.status] || "var(--text-secondary)" }}>
              {plan.gate_preview.assertion} / {plan.gate_preview.status}
            </div>
            {plan.gate_preview.violations.length > 0 && <div style={{ fontSize: 12, color: "var(--red-11)" }}>{plan.gate_preview.violations.join(" ")}</div>}
          </div>

          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{isZh ? "无法推断" : "Not inferable"}</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--text-secondary)" }}>
              {[...plan.not_inferable, ...plan.unresolved].map((text) => <li key={text}>{text}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
