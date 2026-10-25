"use client";

import React, { useState, useEffect } from "react";
import { CockpitState, PerspectiveId, InspectorPayload } from "./types";
import { Locale, getTranslation } from "../../lib/i18n";

interface ValidationLabWorkspaceProps {
  state: CockpitState;
  perspective: PerspectiveId;
  locale?: Locale;
  onOpenInspector: (payload: InspectorPayload) => void;
}

export const ValidationLabWorkspace: React.FC<ValidationLabWorkspaceProps> = ({
  state,
  perspective,
  locale = "zh",
  onOpenInspector,
}) => {
  const t = getTranslation(locale);
  const isZh = locale === "zh";
  const [selectedGridResolution, setSelectedGridResolution] = useState<"16x12" | "12x8">("16x12");
  const [gridData, setGridData] = useState<{ nx: number; ny: number; values: number[][] } | null>(null);
  const [validationReport, setValidationReport] = useState<any>(null);
  const [benchmarkResult, setBenchmarkResult] = useState<any>(null);
  const [whatIfScenario, setWhatIfScenario] = useState<
    "remove_turnover" | "invert_corridor" | "channel_redirection" | "prevent_shot"
  >("remove_turnover");
  const [whatIfResult, setWhatIfResult] = useState<any>(null);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [counterfactualTurnoverReduced, setCounterfactualTurnoverReduced] = useState(25); // percentage
  const [governance, setGovernance] = useState<any>(null);

  const matchId = state.match_id || "syn_default";

  // 0. Model governance contract (Slice C-3): model provenance, training
  // protocol, evaluation interface and heuristic labelling rules.
  useEffect(() => {
    let active = true;
    fetch("/api/models/governance")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) setGovernance(data);
      })
      .catch((err) => console.warn("Failed to load /api/models/governance:", err));
    return () => {
      active = false;
    };
  }, []);

  // 1. Fetch real xT Grid data from backend whenever resolution changes
  useEffect(() => {
    let active = true;
    fetch(`/api/xt/grid?resolution=${selectedGridResolution}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data && data.values) {
          setGridData({
            nx: data.grid_resolution.nx,
            ny: data.grid_resolution.ny,
            values: data.values,
          });
        }
      })
      .catch((err) => console.warn("Failed to load /api/xt/grid:", err));
    return () => {
      active = false;
    };
  }, [selectedGridResolution]);

  // 2. Fetch real Scientific Validation Benchmark Report (Bootstrap CIs & Cross-Match)
  useEffect(() => {
    let active = true;
    fetch(`/api/matches/${matchId}/validation?iterations=50`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) {
          setValidationReport(data);
        }
      })
      .catch((err) => console.warn("Failed to load /api/matches/.../validation:", err));
    return () => {
      active = false;
    };
  }, [matchId]);

  // 3. Fetch real Agent Benchmark A/B/C Deterministic Contract Suite Result
  useEffect(() => {
    let active = true;
    fetch(`/api/benchmark/abc?match_id=${matchId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (active && data) {
          setBenchmarkResult(data);
        }
      })
      .catch((err) => console.warn("Failed to load /api/benchmark/abc:", err));
    return () => {
      active = false;
    };
  }, [matchId]);

  // 4. Trigger real What-If counterfactual simulation
  const executeWhatIfSimulation = async (scenario: string = whatIfScenario) => {
    setWhatIfLoading(true);
    try {
      const res = await fetch(`/api/matches/${matchId}/whatif`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_type: scenario,
          mode: "scenario_based",
          target_corridor: scenario === "channel_redirection" ? "left" : undefined,
        }),
      });
      if (res.ok) {
        const sim = await res.json();
        setWhatIfResult(sim);
      }
    } catch (err) {
      console.warn("Failed to execute What-If simulation:", err);
    } finally {
      setWhatIfLoading(false);
    }
  };

  // Dimensions & fallback values for grid
  const rows = gridData ? gridData.ny : selectedGridResolution === "16x12" ? 12 : 8;
  const cols = gridData ? gridData.nx : selectedGridResolution === "16x12" ? 16 : 12;

  const getXtVal = (r: number, c: number): number => {
    if (gridData && gridData.values[r] && gridData.values[r][c] !== undefined) {
      return gridData.values[r][c];
    }
    const colRatio = c / Math.max(1, cols - 1);
    const rowCenterDist = Math.abs(r - (rows - 1) / 2) / Math.max(1, (rows - 1) / 2);
    const base = 0.008 + colRatio * colRatio * 0.22;
    const centerBonus = (1 - rowCenterDist) * (colRatio > 0.6 ? 0.08 : 0.02);
    return Math.min(0.29, +(base + centerBonus).toFixed(3));
  };

  return (
    <div className="workspace-pane-fade" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 1. Header Banner */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 18px",
          background: "color-mix(in srgb, var(--slate-1) 75%, transparent)",
          border: "0.5px solid var(--glass-border)",
          borderRadius: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>
              {t.validationLabTitle}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() =>
            onOpenInspector({
              type: "sufficiency",
              title: isZh ? "科学数据充分性评估框架" : "Scientific Data Sufficiency Framework",
            })
          }
          style={{
            fontSize: 12,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 6,
            background: "color-mix(in srgb, var(--green-9) 15%, transparent)",
            border: "0.5px solid var(--turf-emerald)",
            color: "var(--text-emerald)",
            cursor: "pointer",
          }}
        >
          {t.viewSufficiencyContract}
        </button>
      </div>

      {/* 2. xT Matrix Contraction & Calibration Suite */}
      <div className="glass-panel" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 800, color: "var(--text-emerald)", textTransform: "uppercase" }}>
              {isZh ? "空间威胁模型" : "Spatial Threat Model"}
            </span>
            <h3 style={{ fontSize: 18, fontWeight: 750, margin: "2px 0 0" }}>
              {t.xtContractionTitle}
            </h3>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{t.gridResolutionLabel}</span>
            <button
              type="button"
              className={`feed-filter-btn ${selectedGridResolution === "16x12" ? "active" : ""}`}
              onClick={() => setSelectedGridResolution("16x12")}
              style={{ fontSize: 12, padding: "3px 8px" }}
            >
              {isZh ? "16 × 12 (细粒度)" : "16 × 12 (Fine)"}
            </button>
            <button
              type="button"
              className={`feed-filter-btn ${selectedGridResolution === "12x8" ? "active" : ""}`}
              onClick={() => setSelectedGridResolution("12x8")}
              style={{ fontSize: 12, padding: "3px 8px" }}
            >
              {isZh ? "12 × 8 (收缩拟合)" : "12 × 8 (Contracted)"}
            </button>
          </div>
        </div>

        {/* Statistical Metrics Row (Backed by Scientific Evaluation Benchmark) */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 100%), 1fr))",
            gap: 10,
            marginBottom: 14,
            padding: "10px 14px",
            background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
            borderRadius: 8,
            border: "0.5px solid var(--pitch-border)",
            textAlign: "center",
          }}
        >
          <div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>MAE ({isZh ? "绝对误差" : "Error"})</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-emerald)" }}>
              {validationReport?.cross_match_mae !== undefined && validationReport?.cross_match_mae !== null ? validationReport.cross_match_mae : "—"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "未运行或未评估" : "Not run / not evaluated"}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>RMSE ({isZh ? "均方根差" : "RMSE"})</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-emerald)" }}>
              {validationReport?.cross_match_rmse !== undefined && validationReport?.cross_match_rmse !== null ? validationReport.cross_match_rmse : "—"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "需实际交叉验证" : "Requires cross-match run"}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>{isZh ? "皮尔逊相关性 r" : "Pearson r"}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-cyan)" }}>
              {validationReport?.cross_match_pearson_r !== undefined && validationReport?.cross_match_pearson_r !== null ? validationReport.cross_match_pearson_r : "—"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{isZh ? "样本不足时不外推" : "No extrapolation on small n"}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>{isZh ? "自举重采样" : "Bootstrap CIs"}</div>
            <div style={{ fontSize: 14, fontWeight: 800, color: "var(--text-gold)" }}>
              {validationReport?.bootstrap_iterations ? `${validationReport.bootstrap_iterations} ${isZh ? "次重采样" : "resamples"}` : (isZh ? "未运行" : "Not run")}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              {validationReport?.monotonicity_preserved ? (isZh ? "静态网格单调性通过" : "Static grid monotonic") : `ID: ${matchId}`}
            </div>
          </div>
        </div>

        {/* Heat Cell Grid Matrix */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
            gap: 3,
            padding: 10,
            background: "color-mix(in srgb, var(--slate-1) 80%, transparent)",
            borderRadius: 8,
            border: "0.5px solid var(--glass-border)",
          }}
        >
          {Array.from({ length: rows }).map((_, r) =>
            Array.from({ length: cols }).map((_, c) => {
              const val = getXtVal(r, c);
              // Color scale from dark green / slate to bright cyan / emerald
              const opacity = Math.min(1, Math.max(0.12, val * 3.5));
              const isBox = c >= 9 && r >= 2 && r <= 5;

              return (
                <div
                  key={`${r}-${c}`}
                  title={`Cell (${r}, ${c}): xT = ${val.toFixed(3)}${isBox ? " (Penalty Box)" : ""}`}
                  style={{
                    height: 28,
                    borderRadius: 3,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontFamily: "monospace",
                    fontWeight: 700,
                    color: val > 0.15 ? "var(--slate-1)" : "var(--text-secondary)",
                    backgroundColor: isBox
                      ? `color-mix(in srgb, var(--green-9) ${Math.round(opacity * 100)}%, transparent)`
                      : `color-mix(in srgb, var(--cyan-9) ${Math.round(opacity * 80)}%, transparent)`,
                    border: isBox
                      ? "0.5px solid color-mix(in srgb, var(--green-9) 50%, transparent)"
                      : "0.5px solid color-mix(in srgb, var(--slate-12) 4%, transparent)",
                    cursor: "pointer",
                    transition: "none",
                  }}
                >
                  {val.toFixed(2)}
                </div>
              );
            })
          )}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-tertiary)", marginTop: 6 }}>
          <span>{isZh ? "← 己方防守三区 (0.005)" : "← Own Defensive Third (0.005)"}</span>
          <span style={{ color: "var(--text-emerald)", fontWeight: 700 }}>
            {isZh ? "对方球门与小禁区危险核心 (0.28+) →" : "Opponent Goal & Six-Yard Box (0.28+) →"}
          </span>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-gold)", lineHeight: 1.5 }}>
          ⚠️ {isZh
            ? "此网格为启发式威胁面（未校验空间先验，非经验拟合）。ΔxT 仅用于成功持球推进（传球/带球），严禁作为铲球、扑救、犯规的通用度量。"
            : "This grid is a heuristic threat surface (uncalibrated spatial prior, not empirically fitted). ΔxT applies to successful ball-retaining progression only — never to tackles, saves or fouls."}
        </div>
      </div>

      {/* 2.5 Model governance (Slice C-3) */}
      <details className="glass-panel" style={{ padding: 18 }} data-testid="model-governance">
        <summary className="mz-summary" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 750, margin: 0 }}>
              {isZh ? "模型治理：xG / xT / OAAI 来源、训练协议与评测" : "Model governance: xG / xT / OAAI provenance and evaluation"}
            </h3>
          </div>
          <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {isZh ? "展开查看" : "Expand"}
          </span>
        </summary>
        <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
          {governance ? (
            Object.entries(governance.models as Record<string, any>).map(([key, model]) => (
              <div key={key} style={{ border: "0.5px solid var(--glass-border)", borderRadius: 8, padding: 12, display: "grid", gap: 6 }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
                  <b style={{ fontSize: 13, color: "var(--text-primary)" }}>{key}</b>
                  {(() => {
                    const status = String(model.model_type || model.model_status || "—");
                    const heuristic = /heuristic|uncalibrated|not_run|not_calibrated/i.test(status);
                    return (
                      <span
                        style={{
                          fontSize: 11,
                          padding: "2px 8px",
                          borderRadius: 999,
                          border: `0.5px solid ${heuristic ? "color-mix(in srgb, var(--amber-9) 45%, transparent)" : "color-mix(in srgb, var(--green-9) 45%, transparent)"}`,
                          color: heuristic ? "var(--text-gold)" : "var(--text-emerald)",
                        }}
                      >
                        {status}
                      </span>
                    );
                  })()}
                  {model.model_version && (
                    <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>v{model.model_version}</span>
                  )}
                </div>
                {model.source && <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{model.source}</div>}
                {model.statement && <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{model.statement}</div>}
                {model.labelling && (
                  <div style={{ fontSize: 12, color: "var(--text-gold)" }}>
                    {isZh ? "标注要求" : "Labelling"}: {model.labelling}
                  </div>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8, marginTop: 4 }}>
                  {model.permitted_uses && (
                    <div style={{ fontSize: 12 }}>
                      <b style={{ color: "var(--text-emerald)" }}>{isZh ? "允许" : "Permitted"}</b>
                      <ul style={{ margin: "4px 0 0", paddingLeft: 16, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                        {model.permitted_uses.map((u: string, i: number) => <li key={i}>{u}</li>)}
                      </ul>
                    </div>
                  )}
                  {model.forbidden_uses && (
                    <div style={{ fontSize: 12 }}>
                      <b style={{ color: "var(--red-11)" }}>{isZh ? "禁止" : "Forbidden"}</b>
                      <ul style={{ margin: "4px 0 0", paddingLeft: 16, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                        {model.forbidden_uses.map((u: string, i: number) => <li key={i}>{u}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
                {model.evaluation_interface && (
                  <div style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                    {Object.values(model.evaluation_interface).join(" · ")}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {isZh ? "加载治理契约..." : "Loading governance contract..."}
            </div>
          )}
          {governance?.inference_levels?.rule && (
            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
              <b>{isZh ? "推理层级纪律" : "Inference-level discipline"}:</b> {governance.inference_levels.rule}
            </div>
          )}
        </div>
      </details>

      {/* 3. Agent A/B/C Benchmark Harness Quantitative Audit Report (collapsed by default) */}
      <details className="glass-panel" style={{ padding: 18 }} data-testid="benchmark-audit">
        <summary className="mz-summary" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 800, color: "var(--text-cyan)", textTransform: "uppercase" }}>
              {isZh ? "智能体契约审计" : "Agent Contract Audit"}
            </span>
            <h3 style={{ fontSize: 18, fontWeight: 750, margin: "2px 0 0" }}>
              {isZh ? "智能体架构 A / B / C 确定性契约对照评测" : "Deterministic Contract Audit: Agent Architecture A / B / C"}
            </h3>
          </div>
          <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
            {isZh ? "审计明细按需展开" : "Expand audit detail"}
          </span>
        </summary>
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
        <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
          {isZh ? "基于规范契约测试集与确定性 Gate 拦截流水线" : "Based on Contract Test Suites & Deterministic Gate Pipeline"}
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="tactical-table">
            <thead>
              <tr>
                <th>{isZh ? "流水线配置" : "Pipeline"}</th>
                <th>{isZh ? "执行组件" : "Executed components"}</th>
                <th>{isZh ? "无效声明拦截率" : "Invalid block rate"}</th>
                <th>{isZh ? "契约一致率" : "Contract agreement"}</th>
                <th>{isZh ? "在线模型" : "Live model"}</th>
                <th>{isZh ? "Token 成本" : "Token cost"}</th>
                <th>{isZh ? "实测延迟" : "Measured latency"}</th>
                <th>{isZh ? "工具状态" : "Tools"}</th>
              </tr>
            </thead>
            <tbody>
              {benchmarkResult?.configurations && benchmarkResult.configurations.length > 0 ? (
                benchmarkResult.configurations.map((cfg: any) => {
                  const labels: Record<string, { name: string; tools: string }> = {
                    A_reference_only: {
                      name: isZh ? "配置 A 仅引用校验" : "A Reference only",
                      tools: isZh ? "事件 ID 存在性检查" : "Event-ID existence",
                    },
                    B_gate20: {
                      name: isZh ? "配置 B Gate 2.0" : "B Gate 2.0",
                      tools: isZh ? "规则引擎（措辞/假设/版本）" : "Rule engine (wording/assumptions/version)",
                    },
                    C_gate20_plus_tools: {
                      name: isZh ? "配置 C Gate + 工具" : "C Gate + tools",
                      tools: isZh ? "门禁 + 确定性归因工具" : "Gate + deterministic attribution tools",
                    },
                  };
                  const meta = labels[cfg.config] || { name: cfg.config, tools: "—" };
                  const block = typeof cfg.invalid_block_rate === "number" ? `${(cfg.invalid_block_rate * 100).toFixed(1)}%` : "n/a";
                  const agreement = typeof cfg.contract_agreement_rate === "number" ? `${(cfg.contract_agreement_rate * 100).toFixed(1)}%` : "n/a";
                  return (
                    <tr key={cfg.config}>
                      <td><b>{meta.name}</b></td>
                      <td>{meta.tools}</td>
                      <td style={{ fontWeight: 750 }}>{block}</td>
                      <td>{agreement}</td>
                      <td>{benchmarkResult?.live_model_status === "not_run" ? "Not Run" : "Run"}</td>
                      <td>—</td>
                      <td>{typeof cfg.latency_ms_measured === "number" ? `${cfg.latency_ms_measured.toFixed(1)}ms` : "—"}</td>
                      <td>
                        <span style={{ color: cfg.alternative_hypothesis_tool_executed ? "var(--text-emerald)" : "var(--text-tertiary)", fontWeight: 700 }}>
                          {cfg.alternative_hypothesis_tool_executed ? (isZh ? "工具已执行" : "Tools run") : (isZh ? "未执行" : "Not run")}
                        </span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} style={{ color: "var(--text-tertiary)", padding: 16 }}>
                    {isZh ? "尚无已执行的基准结果。" : "No executed benchmark result."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: 12, padding: "10px 14px", background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", borderRadius: 6, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          <b>{isZh ? "评测口径说明" : "Benchmark scope"}</b>: {benchmarkResult?.summary || (isZh
            ? "确定性契约基准尚未运行。此处不展示任何预设准确率、成本或延迟数字。"
            : "No deterministic contract benchmark has run. No preset accuracy, cost or latency values are displayed here.")}
        </div>
        </div>
      </details>

      {/* 4. What-if Counterfactual Research Sandbox (Level 3 Exploratory) */}
      <div className="glass-panel" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 800, color: "var(--text-gold)", textTransform: "uppercase" }}>
              {isZh ? "探索性推演" : "Exploratory Simulation"}
            </span>
            <h3 style={{ fontSize: 18, fontWeight: 750, margin: "2px 0 0" }}>
              {isZh ? "What-If 反事实推演沙盒 (模拟战术干预)" : "What-If Counterfactual Sandbox (Simulated Interventions)"}
            </h3>
          </div>

          <span
            style={{
              fontSize: 12,
              fontWeight: 750,
              padding: "3px 8px",
              borderRadius: 6,
              background: "color-mix(in srgb, var(--amber-9) 15%, transparent)",
              border: "0.5px solid color-mix(in srgb, var(--amber-9) 40%, transparent)",
              color: "var(--text-gold)",
            }}
          >
            {isZh ? "⚠️ 严谨科研提示：仅限探索实验 — 不作为正式转播结论" : "⚠️ RESEARCH ONLY — NOT FOR OFFICIAL BROADCAST"}
          </span>
        </div>

        {/* Scenario Selection Buttons */}
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>
            {isZh ? "选择战术干预场景:" : "Intervention Scenario:"}
          </span>
          {[
            { id: "remove_turnover", label: isZh ? "消除关键失误" : "Remove Turnover" },
            { id: "invert_corridor", label: isZh ? "镜像对策走廊" : "Invert Corridor" },
            { id: "channel_redirection", label: isZh ? "左路通道重定向" : "Redirect to Left" },
            { id: "prevent_shot", label: isZh ? "封堵危险射门" : "Prevent Shot" },
          ].map((sc) => (
            <button
              key={sc.id}
              type="button"
              className={`feed-filter-btn ${whatIfScenario === sc.id ? "active" : ""}`}
              onClick={() => {
                setWhatIfScenario(sc.id as any);
                executeWhatIfSimulation(sc.id);
              }}
              style={{ fontSize: 12, padding: "4px 10px" }}
            >
              {sc.label}
            </button>
          ))}

          <button
            type="button"
            disabled={whatIfLoading}
            onClick={() => executeWhatIfSimulation(whatIfScenario)}
            style={{
              fontSize: 12,
              fontWeight: 750,
              padding: "4px 12px",
              borderRadius: 6,
              background: "var(--turf-emerald)",
              color: "var(--slate-1)",
              border: "none",
              cursor: "pointer",
              marginLeft: "auto",
            }}
          >
            {whatIfLoading ? (isZh ? "推演中..." : "Simulating...") : (isZh ? "▶ 运行数学反事实推演" : "▶ Run Simulation")}
          </button>
        </div>

        {/* Simulation Output Cards */}
        {whatIfResult && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(min(150px, 100%), 1fr))",
              gap: 8,
              padding: "10px 14px",
              background: "color-mix(in srgb, var(--green-9) 8%, transparent)",
              border: "0.5px solid color-mix(in srgb, var(--green-9) 30%, transparent)",
              borderRadius: 8,
              marginBottom: 12,
              textAlign: "center",
            }}
          >
            <div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Δ OAAI 动量幅度</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: whatIfResult.delta_oaai_amplitude >= 0 ? "var(--text-emerald)" : "var(--crimson-warn)" }}>
                {whatIfResult.delta_oaai_amplitude > 0 ? `+${whatIfResult.delta_oaai_amplitude}` : whatIfResult.delta_oaai_amplitude}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Δ xT 威胁增量</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-cyan)" }}>
                {whatIfResult.delta_threat > 0 ? `+${whatIfResult.delta_threat}` : whatIfResult.delta_threat}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>Δ xG 期望进球</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-gold)" }}>
                {whatIfResult.delta_xg > 0 ? `+${whatIfResult.delta_xg}` : whatIfResult.delta_xg}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)", textTransform: "uppercase" }}>受影响事件数</div>
              <div style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)" }}>
                {whatIfResult.affected_events_count} {isZh ? "个" : "events"}
              </div>
            </div>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(300px, 100%), 1fr))", gap: 14 }}>
          <div style={{ padding: 12, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", borderRadius: 8, border: "0.5px solid var(--pitch-border)" }}>
            <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "var(--text-primary)", marginBottom: 6 }}>
              {isZh ? `模拟减少后场关键防守失误率: ${counterfactualTurnoverReduced}%` : `Simulated Reduction in Defensive Turnover Rate: ${counterfactualTurnoverReduced}%`}
            </label>
            <input
              type="range"
              min={0}
              max={50}
              value={counterfactualTurnoverReduced}
              onChange={(e) => setCounterfactualTurnoverReduced(Number(e.target.value))}
              style={{ width: "100%", accentColor: "var(--turf-emerald)" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-tertiary)", marginTop: 4 }}>
              <span>{isZh ? "基线现状 (0%)" : "Baseline (0%)"}</span>
              <span>{isZh ? "最大抑制 (50%)" : "Maximum Suppression (50%)"}</span>
            </div>
          </div>

          <div style={{ padding: 12, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", borderRadius: 8, border: "0.5px solid var(--pitch-border)", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
              {isZh ? `反事实观察边界 (失误抑制 ${counterfactualTurnoverReduced}%):` : `Observational Counterfactual Boundary (${counterfactualTurnoverReduced}% Turnover Suppression):`}
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-emerald)", marginTop: 4 }}>
              {isZh ? "潜在转换射门抑制: " : "Potential Transition Shots Suppressed: "}~{((Number(state.receipts?.[`${state.focus_team || "H"}.transition_shots.current`]?.value || 2) * counterfactualTurnoverReduced) / 100).toFixed(1)} {isZh ? "次起脚" : "shots"}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 4, lineHeight: 1.4 }}>
              {whatIfResult?.disclaimer || (isZh ? "发布门禁边界守则: 缺乏22人全场追踪与体能负荷数据，严禁将失误率直接线性换算为胜率或教练意图因果。" : "No 22-player tracking: turnover counts cannot be converted to win probability.")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
