"use client";

import React, { useState } from "react";
import { Locale } from "../../lib/i18n";

interface TacticalGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  locale: Locale;
}

export const TacticalGuideModal: React.FC<TacticalGuideModalProps> = ({
  isOpen,
  onClose,
  locale,
}) => {
  const [activeTab, setActiveTab] = useState<"oaai" | "s2_s3" | "corridors" | "recovery" | "gate" | "shortcuts">("oaai");

  if (!isOpen) return null;

  const isZh = locale === "zh";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "color-mix(in srgb, var(--slate-1) 80%, transparent)",
        backdropFilter: "blur(8px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "840px",
          maxHeight: "88vh",
          background: "var(--slate-1)",
          border: "0.5px solid var(--glass-border)",
          borderRadius: "var(--radius-panel)",
          boxShadow: "none",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "color-mix(in srgb, var(--slate-1) 60%, transparent)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 18 }}>📖</span>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--text-primary)" }}>
                {isZh ? "MatchLens AI 战术指标指南与使用释义" : "MatchLens AI Tactical Indicators & Glossary"}
              </h2>
              <p style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                {isZh ? "帮助您快速理解各项核心数据、计算逻辑与避免视觉疲劳" : "Quick reference to metric formulas, tactical definitions, and shortcuts"}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "color-mix(in srgb, var(--slate-12) 5%, transparent)",
              border: "0.5px solid color-mix(in srgb, var(--slate-12) 10%, transparent)",
              borderRadius: "8px",
              color: "var(--text-secondary)",
              fontSize: 18,
              padding: "4px 10px",
              cursor: "pointer",
              minHeight: "auto",
            }}
          >
            ✕
          </button>
        </div>

        {/* Navigation Tabs */}
        <div
          style={{
            display: "flex",
            borderBottom: "0.5px solid color-mix(in srgb, var(--slate-12) 6%, transparent)",
            background: "color-mix(in srgb, var(--slate-1) 70%, transparent)",
            padding: "0 16px",
            gap: 8,
            overflowX: "auto",
          }}
        >
          {[
            { id: "oaai", labelZh: "1. OAAI 攻防动量", labelEn: "1. OAAI Momentum" },
            { id: "s2_s3", labelZh: "2. S2 序列与九宫格", labelEn: "2. S2 & S3 Zones" },
            { id: "corridors", labelZh: "3. 进攻三走廊", labelEn: "3. Attacking Corridors" },
            { id: "recovery", labelZh: "4. 6s 反抢恢复", labelEn: "4. 6s Recovery" },
            { id: "gate", labelZh: "5. Publication Gate 门禁", labelEn: "5. Publication Gate" },
            { id: "shortcuts", labelZh: "6. 快捷操作指引", labelEn: "6. Shortcuts & Tips" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                background: "transparent",
                border: "none",
                borderBottom: activeTab === tab.id ? "0.5px solid var(--turf-emerald)" : "0.5px solid transparent",
                color: activeTab === tab.id ? "var(--turf-emerald)" : "var(--text-secondary)",
                fontWeight: activeTab === tab.id ? 700 : 500,
                fontSize: 14,
                padding: "12px 14px",
                borderRadius: 0,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {isZh ? tab.labelZh : tab.labelEn}
            </button>
          ))}
        </div>

        {/* Modal Content Body */}
        <div
          style={{
            padding: "24px",
            overflowY: "auto",
            flex: 1,
            color: "var(--text-secondary)",
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          {/* TAB 1: OAAI */}
          {activeTab === "oaai" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "10px",
                  background: "color-mix(in srgb, var(--green-9) 10%, transparent)",
                  border: "0.5px solid color-mix(in srgb, var(--green-9) 25%, transparent)",
                  color: "var(--text-emerald)",
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {isZh
                  ? "💡 核心公式：OAAI = λ xT_gain + μ final_third_entries + ν box_actions。度量已记录客观事件聚合的攻防活动强度。"
                  : "💡 Core formula: OAAI aggregates spatial xT gain, final third entries, and box events into objective attack intensity."}
              </div>

              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "如何阅读 OAAI 攻防动量波浪图？" : "How to Read the OAAI Momentum Wave?"}
              </h4>
              <ul style={{ paddingLeft: 20, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                <li>
                  <strong style={{ color: "var(--text-emerald)" }}>{isZh ? "零轴上方 (+)" : "Above Zero Line (+)"}: </strong>
                  {isZh
                    ? "主队（Harbor FC）处于进攻推进强势期，连续产生高价值向前传球、前场逼抢或射门。"
                    : "Home team (Harbor FC) dominates attacking progression and forward territorial pressure."}
                </li>
                <li>
                  <strong style={{ color: "var(--text-cyan)" }}>{isZh ? "零轴下方 (-)" : "Below Zero Line (-)"}: </strong>
                  {isZh
                    ? "客队（Northbridge United）压制或打出快速防守反击，主导进攻活动。"
                    : "Away side (Northbridge United) is applying counter-pressure or dominating attacking sequences."}
                </li>
                <li>
                  <strong style={{ color: "var(--text-gold)" }}>{isZh ? "CP 变化点 (Change-Points)" : "Change-Points (CP Icons)"}: </strong>
                  {isZh
                    ? "图上的圆圈（CP-01, CP-02...）表示攻防动量发生突变的关键节点。点击圆圈可直接查看驱动该突变的 Top 支撑动作与归因分解。"
                    : "Circles represent statistical momentum inflection points. Click any CP to see causal event attribution."}
                </li>
                <li>
                  <strong style={{ color: "var(--text-primary)" }}>{isZh ? "因果滤波 vs 赛后双边平滑" : "Causal vs. Bilateral Smoothing"}: </strong>
                  {isZh
                    ? "实时因果滤波（Causal）仅计算当前时钟以前的事件，符合直播实况推演；赛后双边平滑（Bilateral）使用前后对称卷积核，波形更加优雅平滑，适合赛后全场复盘。"
                    : "Causal mode only uses historical data (<= t) for live streaming; Bilateral mode uses forward-backward smoothing for post-match analysis."}
                </li>
              </ul>
            </div>
          )}

          {/* TAB 2: S2 & S3 */}
          {activeTab === "s2_s3" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "S2 控球序列与 S3 九宫格双向联动" : "S2 Possession Sequences & S3 Dual Drilldown"}
              </h4>
              <p>
                {isZh
                  ? "现代足球分析强调连续控球动作构成的完整攻守链条（Possession Sequence），而非孤立的点状事件。"
                  : "Modern football analysis links isolated events into cohesive possession sequences and spatial zones."}
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <div style={{ padding: 14, borderRadius: 10, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <div style={{ fontWeight: 700, color: "var(--text-cyan)", marginBottom: 6 }}>
                    {isZh ? "S2: 控球序列 (Sequences)" : "S2: Possession Sequences"}
                  </div>
                  <div style={{ fontSize: 14 }}>
                    {isZh
                      ? "定义：同一球队连续无间断触球构成的攻防段落。记录向前净推进距离、触球脚数、是否打入前场三区以及最终结果（射门/被断/界外）。"
                      : "Sequences track continuous passes, progressive distance gained, final third entry, and outcome."}
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 10, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <div style={{ fontWeight: 700, color: "var(--text-emerald)", marginBottom: 6 }}>
                    {isZh ? "S3: 行动密度差分 ΔD(z)" : "S3: Density Differential ΔD(z)"}
                  </div>
                  <div style={{ fontSize: 14 }}>
                    {isZh
                      ? "定义：将球场划分为九宫格（防守/中场/进攻 × 左/中/右）。ΔD(z) 计算两队在特定区域的行动占比差，差值为正代表主队占优，为负代表客队占优。"
                      : "Pitch divided into a 3x3 grid. ΔD(z) measures the action share difference between both teams."}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 14, background: "color-mix(in srgb, var(--cyan-9) 10%, transparent)", padding: 12, borderRadius: 8, border: "0.5px solid color-mix(in srgb, var(--cyan-9) 20%, transparent)" }}>
                {isZh
                  ? "⚡ 双向联动下钻：在战术实验室中，点击九宫格区域可瞬间筛选跨越该区域的所有 S2 序列；点击任意序列则可在球场上高亮其完整轨迹。"
                  : "⚡ Bidirectional linkage: Click any zone to filter crossing sequences; click a sequence to inspect its pitch path."}
              </div>
            </div>
          )}

          {/* TAB 3: Corridors */}
          {activeTab === "corridors" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "BL-08 进攻三走廊划分与渗透度" : "BL-08 Attacking Corridor Progression"}
              </h4>
              <p>
                {isZh
                  ? "为了避免因两队攻守方向对调导致的左右混淆，MatchLens 严格采用【本队进攻球门视角】对走廊进行归一化划分："
                  : "Corridors are normalized relative to each team's attacking direction to eliminate orientation confusion:"}
              </p>
              <ul style={{ paddingLeft: 20, margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
                <li>
                  <strong>{isZh ? "左路走廊 (Left Flank)" : "Left Flank"}: </strong>
                  {isZh ? "边锋内切与左后卫叠瓦套上主攻通道。" : "Wide winger isolations and overlapping fullback runs."}
                </li>
                <li>
                  <strong>{isZh ? "中路主轴 (Central Core)" : "Central Core"}: </strong>
                  {isZh ? "直塞中锋、前腰渗透及禁区前沿直塞最具杀伤力的中轴线。" : "Through balls, central playmaking, and direct box entries."}
                </li>
                <li>
                  <strong>{isZh ? "右路走廊 (Right Flank)" : "Right Flank"}: </strong>
                  {isZh ? "边路传中、逆足拉开与弱侧转移接应点。" : "Cross deliveries, winger 1v1s, and switch of play targets."}
                </li>
                <li>
                  <strong style={{ color: "var(--text-emerald)" }}>{isZh ? "禁区触球转化率" : "Box Conversion Rate"}: </strong>
                  {isZh
                    ? "进入禁区后的触球转化成射门的比例。转化率越高代表该走廊进攻终结效率极高。"
                    : "Percentage of penalty area touches converted into actual shots."}
                </li>
              </ul>
            </div>
          )}

          {/* TAB 4: 6s Recovery */}
          {activeTab === "recovery" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "BL-03 失去球权后 6 秒快速恢复率" : "BL-03 Post-Turnover 6-Second Quick Recovery"}
              </h4>
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: "10px",
                  background: "color-mix(in srgb, var(--amber-9) 10%, transparent)",
                  border: "0.5px solid color-mix(in srgb, var(--amber-9) 25%, transparent)",
                  color: "var(--text-gold)",
                  fontSize: 14,
                }}
              >
                {isZh
                  ? "⚠️ 数据充分性特别说明：常规赛事事件流（非骨骼或全场22人追踪数据）缺少连续的无球防守阵型位置，因此无法直接断言阵型紧凑度；但 6 秒反抢恢复率是一项经科学验证的可观察有效代理指标。"
                  : "⚠️ Data Sufficiency Note: Standard event streams lack 22-player tracking. 6-second recovery serves as a validated observable proxy for counterpressing intensity."}
              </div>
              <p>
                {isZh
                  ? "瓜迪奥拉与克洛普的高位反抢战术（Gegenpressing）核心在于：球权丢失后的 3–6 秒内对手防线尚未展开，此时反抢成功率最高且可就地发起致命突袭。"
                  : "The 6-second window quantifies Gegenpressing efficiency—recovering the ball before the opponent transitions into shape."}
              </p>
            </div>
          )}

          {/* TAB 5: Publication Gate */}
          {activeTab === "gate" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "Publication Publication Gate 严谨防幻觉门禁" : "Publication Publication Gate Guardrail Architecture"}
              </h4>
              <p>
                {isZh
                  ? "MatchLens 坚决杜绝 AI 常见的故事编造与虚假因果，所有观点均受 Publication Gate 分级约束："
                  : "MatchLens eliminates AI hallucination by enforcing deterministic claim levels:"}
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--green-9) 8%, transparent)", border: "0.5px solid color-mix(in srgb, var(--green-9) 20%, transparent)" }}>
                  <span style={{ fontWeight: 800, color: "var(--text-emerald)" }}>Level 1: 纯客观观察事实 (Direct Observation)</span>
                  <div style={{ fontSize: 14, marginTop: 4 }}>
                    {isZh ? "严格基于事件计数（如：中路完成了 5 次进攻发起、传球成功率 82%）。无任何主观推测。" : "Pure empirical counts from logs with zero subjective speculation."}
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--cyan-9) 8%, transparent)", border: "0.5px solid color-mix(in srgb, var(--cyan-9) 20%, transparent)" }}>
                  <span style={{ fontWeight: 800, color: "var(--text-cyan)" }}>Level 2: 公式化指标分解 (Deterministic Decomposition)</span>
                  <div style={{ fontSize: 14, marginTop: 4 }}>
                    {isZh ? "通过明确数学公式分解出的衍生指标（如：OAAI 贡献分解、xT 期望威胁增量）。" : "Derived metrics computed via deterministic mathematical formulas (OAAI, xT)."}
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--red-9) 8%, transparent)", border: "0.5px solid color-mix(in srgb, var(--red-9) 20%, transparent)" }}>
                  <span style={{ fontWeight: 800, color: "var(--red-11)" }}>Level 3: 假设与科研反事实 (Hypothetical & What-If)</span>
                  <div style={{ fontSize: 14, marginTop: 4 }}>
                    {isZh ? "必须标注前提假设与验证方法，未检索到对立反证且经人工复核前严禁宣称确定因果。" : "Exploratory counterfactuals requiring explicit assumptions and counterevidence audit."}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: Shortcuts */}
          {activeTab === "shortcuts" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <h4 style={{ color: "var(--text-primary)", fontWeight: 700, fontSize: 18 }}>
                {isZh ? "交互快捷技巧与键盘操作" : "Shortcuts & Productivity Tips"}
              </h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <code style={{ color: "var(--text-cyan)", fontWeight: 700 }}>Spacebar (空格)</code>
                  <div style={{ fontSize: 14, marginTop: 4 }}>{isZh ? "一键暂停 / 继续比赛模拟时钟" : "Toggle Play / Pause match replay"}</div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <code style={{ color: "var(--text-cyan)", fontWeight: 700 }}>Timeline Slider (拖动)</code>
                  <div style={{ fontSize: 14, marginTop: 4 }}>{isZh ? "全局任意快进、快退到目标比赛时段" : "Scrub playback instantly to any second"}</div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <code style={{ color: "var(--text-cyan)", fontWeight: 700 }}>🔍 Inspector Drawer</code>
                  <div style={{ fontSize: 14, marginTop: 4 }}>{isZh ? "右侧详情抽屉，点击任意事件或序列不阻断主视野" : "Non-blocking slide-out drawer for deep dives"}</div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: "color-mix(in srgb, var(--slate-1) 60%, transparent)", border: "0.5px solid var(--glass-border)" }}>
                  <code style={{ color: "var(--text-cyan)", fontWeight: 700 }}>中 / EN Toggle</code>
                  <div style={{ fontSize: 14, marginTop: 4 }}>{isZh ? "右上角一键切换全站中英文界面" : "One-click bilingual interface switcher"}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "0.5px solid color-mix(in srgb, var(--slate-12) 8%, transparent)",
            display: "flex",
            justifyContent: "flex-end",
            background: "color-mix(in srgb, var(--slate-1) 80%, transparent)",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "6px 20px",
              borderRadius: "8px",
              background: "var(--turf-emerald)",
              color: "var(--green-3)",
              fontWeight: 800,
              fontSize: 14,
              border: "none",
              cursor: "pointer",
            }}
          >
            {isZh ? "我知道了，返回比赛分析" : "Got it, back to Cockpit"}
          </button>
        </div>
      </div>
    </div>
  );
};
