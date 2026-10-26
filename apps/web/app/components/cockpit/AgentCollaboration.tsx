"use client";

import React from "react";
import { Locale } from "../../lib/i18n";

/**
 * Who produced this plan, and what each stage actually did.
 *
 * The rule this component exists to enforce: it renders only the stages that
 * really ran. A deterministic plan has no analyst or verifier to show, so it
 * says "no model was called" instead of staging a two-agent conversation. A
 * model-backed plan shows the tool each stage called and the verifier's own
 * per-claim decision, so the division of labour is visible without opening the
 * raw trace.
 */
export type CollaborationSummary = {
  mode: "maf_agent" | "deterministic_planner";
  model: string | null;
  requests: number;
  stages: string[];
  analyst: {
    tool_calls: number;
    tools: string[];
    claim_id: string | null;
    assertion: string | null;
    draft_sha256: string | null;
  } | null;
  verifier: {
    tool_calls: number;
    tools: string[];
    counterevidence_checked: boolean;
    decisions: {
      claim_id: string;
      verdict: string;
      selected_variant: string | null;
      reason: string;
      limitations: string[];
    }[];
  } | null;
  gate: { status: string; violations: string[] };
};

interface AgentCollaborationProps {
  collaboration?: CollaborationSummary | null;
  stateHistory?: { state: string; reason?: string }[];
  toolReceiptCount?: number;
  agentStatus?: string;
  agentError?: string | null;
  locale?: Locale;
}

const verdictTone: Record<string, string> = {
  publish: "var(--text-emerald)",
  approved: "var(--text-emerald)",
  qualify: "var(--gold, var(--amber-gold))",
  qualified: "var(--gold, var(--amber-gold))",
  withhold: "var(--red-11)",
  withheld: "var(--red-11)",
  rejected: "var(--red-11)",
};

export const AgentCollaboration: React.FC<AgentCollaborationProps> = ({
  collaboration,
  stateHistory = [],
  toolReceiptCount = 0,
  agentStatus = "not_run",
  agentError = null,
  locale = "zh",
}) => {
  const isZh = locale === "zh";
  if (!collaboration) return null;

  const live = collaboration.mode === "maf_agent";
  const gateTone = verdictTone[collaboration.gate.status] || "var(--text-secondary)";

  return (
    <section
      className="r6-collab"
      data-testid="agent-collaboration"
      data-mode={collaboration.mode}
      data-agent-status={agentStatus}
      aria-label={isZh ? "协作过程" : "Collaboration"}
    >
      <header className="r6-collab-head">
        <h5>{live ? (isZh ? "两个 Agent 的分工" : "How the two agents divided the work") : isZh ? "确定性调查" : "Deterministic investigation"}</h5>
        <span className="r6-collab-mode" data-live={live ? "true" : "false"}>
          {live
            ? isZh
              ? `真实模型 · ${collaboration.model || "model"} · ${collaboration.requests} 次请求`
              : `Live model · ${collaboration.model || "model"} · ${collaboration.requests} request${collaboration.requests === 1 ? "" : "s"}`
            : isZh
              ? "未调用模型 · 确定性工具"
              : "No model called · deterministic tools"}
        </span>
      </header>

      {live ? (
        <ol className="r6-collab-flow">
          <li data-testid="collab-analyst" data-stage="analyst">
            <span className="r6-collab-role">Analyst</span>
            <b>{collaboration.analyst?.claim_id || "—"}</b>
            <p>
              {isZh ? "自选工具后提出主张" : "Chose its own tools, then proposed a claim"}:{" "}
              <code>{collaboration.analyst?.assertion || "—"}</code>
            </p>
            <small>
              {collaboration.analyst?.tool_calls ?? 0} {isZh ? "次工具调用" : "tool calls"}
              {collaboration.analyst?.tools?.length ? ` · ${collaboration.analyst.tools.join(", ")}` : ""}
            </small>
          </li>
          <li data-testid="collab-verifier" data-stage="verifier">
            <span className="r6-collab-role">Verifier</span>
            <b>
              {(collaboration.verifier?.decisions || [])
                .map((decision) => decision.verdict)
                .join(" / ") || (isZh ? "未形成裁决" : "no verdict")}
            </b>
            <p>
              {collaboration.verifier?.counterevidence_checked
                ? isZh
                  ? "独立调用工具核对，并主动查了反证。"
                  : "Ran its own tools and checked counterevidence."
                : isZh
                  ? "独立调用工具核对，未查反证。"
                  : "Ran its own tools; no counterevidence query."}
            </p>
            {collaboration.verifier?.decisions?.map((decision) => (
              <div key={decision.claim_id} className="r6-collab-decision" data-verdict={decision.verdict}>
                <span style={{ color: verdictTone[decision.verdict] || "var(--text-secondary)" }}>
                  {decision.verdict}
                  {decision.selected_variant ? ` · ${decision.selected_variant}` : ""}
                </span>
                <em>{decision.reason}</em>
              </div>
            ))}
            <small>
              {collaboration.verifier?.tool_calls ?? 0} {isZh ? "次工具调用" : "tool calls"}
              {collaboration.verifier?.tools?.length ? ` · ${collaboration.verifier.tools.join(", ")}` : ""}
            </small>
          </li>
          <li data-testid="collab-gate" data-stage="gate">
            <span className="r6-collab-role">{isZh ? "门禁" : "Gate"}</span>
            <b style={{ color: gateTone }}>{collaboration.gate.status}</b>
            <p>
              {collaboration.gate.violations.length
                ? collaboration.gate.violations.join(" ")
                : isZh
                  ? "未发现可发布的违规项。"
                  : "No publishable violation found."}
            </p>
          </li>
        </ol>
      ) : (
        <div className="r6-collab-one" data-testid="collab-deterministic">
          <p>
            {isZh
              ? "这份计划由确定性引擎生成：同样的输入永远得到同样的数字与结论，没有模型参与，因此也没有 Analyst/Verifier 对话。"
              : "This plan came from the deterministic engine: the same input always yields the same numbers and conclusion, no model took part, and therefore no Analyst/Verifier exchange exists."}
          </p>
          <small>
            {toolReceiptCount} {isZh ? "次工具调用" : "tool calls"}
            {collaboration.stages.length ? ` · ${collaboration.stages.join(" → ")}` : ""}
          </small>
        </div>
      )}

      {agentStatus === "failed" && (
        <div className="r6-collab-degraded" data-testid="collab-degraded">
          {isZh
            ? `真实 Agent 本次失败（${agentError || "unknown"}），已安全降级为确定性结果。`
            : `The live agent run failed (${agentError || "unknown"}); this is the safe deterministic fallback.`}
        </div>
      )}

      {!live && stateHistory.length > 0 && (
        <details className="r6-collab-stages">
          <summary>{isZh ? "确定性阶段" : "Deterministic stages"}</summary>
          <ol>
            {stateHistory.map((entry, index) => (
              <li key={`${entry.state}-${index}`}>
                <b>{entry.state}</b>
                {entry.reason ? <span> — {entry.reason}</span> : null}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
};
