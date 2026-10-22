"use client";

import { Locale } from "../lib/i18n";

type Receipt = {
  id: string;
  value: number;
  unit: string;
};

type MetricComparisonProps = {
  receipts: Record<string, Receipt>;
  at: number;
  snapshotId: string | null;
  focusTeam?: "H" | "N";
  locale?: Locale;
  onInspect: (receiptId: string) => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

const labelsZh: Record<string, string> = {
  possession: "有效控球率",
  shots: "射门尝试次数",
  entries: "推进进前场 (x=70m)",
  high_recoveries: "前场高位反抢",
  transition_shots: "反抢就地射门 (≤10s)",
};

const labelsEn: Record<string, string> = {
  possession: "Controlled Possession",
  shots: "Shot Attempts",
  entries: "Attacking Entries (x=70m)",
  high_recoveries: "High Recoveries",
  transition_shots: "Recovery → Shot (≤10s)",
};

export function MetricComparison({
  receipts,
  at,
  snapshotId,
  focusTeam = "H",
  locale = "zh",
  onInspect,
}: MetricComparisonProps) {
  const isZh = locale === "zh";
  const labels = isZh ? labelsZh : labelsEn;
  const prevStart = Math.max(0, at - 360);
  const prevEnd = Math.max(0, at - 180);
  const currStart = prevEnd;
  const currEnd = at;
  const teamLabel = focusTeam === "N" ? "Northbridge Utd" : "Harbor FC";

  const metrics = [
    "possession",
    "shots",
    "entries",
    "high_recoveries",
    "transition_shots",
  ];

  const prevDuration = prevEnd - prevStart;
  const currDuration = currEnd - currStart;
  const isSampleInsufficient = at < 180;
  const isSingleWindow = at >= 180 && at < 360;

  return (
    <section className="metric-comparison-card" aria-label="Window Metric Delta Comparison">
      <div className="comparison-header">
        <div className="header-title-wrap">
          <span className="comparison-tag">
            {isZh ? `战术指标变化 · ${teamLabel.toUpperCase()}` : `TACTICAL METRICS DELTA · ${teamLabel.toUpperCase()}`}
          </span>
          <h3 className="comparison-title">
            {isZh ? `3分钟滑动窗口对比 (${teamLabel})` : `3-Minute Window Comparison (${teamLabel})`}
          </h3>
        </div>
        <div className="comparison-windows">
          <span className="window-pill prev" title={isZh ? `上一窗口: ${prevDuration}秒时长` : `Previous window: ${prevDuration}s duration`}>
            {clock(prevStart)}–{clock(prevEnd)} ({prevDuration}s)
          </span>
          <span className="window-arrow">→</span>
          <span className="window-pill curr" title={isZh ? `当前窗口: ${currDuration}秒时长` : `Current window: ${currDuration}s duration`}>
            {clock(currStart)}–{clock(currEnd)} ({currDuration}s)
          </span>
        </div>
      </div>

      {isSampleInsufficient && (
        <div className="window-sample-warning" role="status" style={{
          padding: "6px 12px",
          margin: "8px 0 12px",
          borderRadius: "6px",
          background: "rgba(245, 158, 11, 0.1)",
          border: "1px solid rgba(245, 158, 11, 0.3)",
          color: "var(--text-gold)",
          fontSize: "12px",
          fontWeight: 600,
        }}>
          {isZh
            ? "⚠️ 比赛开场阶段 (t < 3m): 样本量不足以构成两个独立的 180s 对比窗口。"
            : "⚠️ Early match stage (t < 3m): insufficient sample for two distinct 180s comparison windows."}
        </div>
      )}

      {isSingleWindow && (
        <div className="window-sample-warning" role="status" style={{
          padding: "6px 12px",
          margin: "8px 0 12px",
          borderRadius: "6px",
          background: "rgba(59, 130, 246, 0.08)",
          border: "1px solid rgba(59, 130, 246, 0.25)",
          color: "var(--ice-blue)",
          fontSize: "12px",
          fontWeight: 500,
        }}>
          {isZh
            ? "ℹ️ 单基准窗口生效中 (00:00–03:00)；上一窗口表示开场初始基准线。"
            : "ℹ️ Single baseline window active (00:00–03:00); previous window represents opening baseline."}
        </div>
      )}

      <div className="comparison-table">
        <div className="table-head">
          <span>{isZh ? "战术指标" : "METRIC"}</span>
          <span>{isZh ? "上一窗口" : "PREVIOUS"}</span>
          <span className="col-bar">{isZh ? "变化对比图" : "DELTA VISUALIZER"}</span>
          <span>{isZh ? "当前窗口" : "CURRENT"}</span>
        </div>

        {metrics.map((m) => {
          const prev = receipts[`${focusTeam}.${m}.previous`];
          const curr = receipts[`${focusTeam}.${m}.current`];
          if (!prev || !curr) return null;

          const maxVal = m === "possession" ? 100 : Math.max(4, prev.value, curr.value);
          const prevPct = Math.min(100, (prev.value / maxVal) * 100);
          const currPct = Math.min(100, (curr.value / maxVal) * 100);

          const isUp = curr.value > prev.value;
          const isDown = curr.value < prev.value;

          return (
            <button
              key={m}
              type="button"
              className="metric-row-btn"
              onClick={() => onInspect(curr.id)}
              disabled={!snapshotId}
              title={isZh ? `点击审计 ${labels[m]} 证据凭证与计算链` : `Click to inspect ${labels[m]} evidence receipt`}
            >
              <span className="metric-label">
                {labels[m]}
                <span className="inspect-hint">↗</span>
              </span>
              <span className="metric-val prev">{prev.value}{prev.unit === "%" ? "%" : ""}</span>
              <span className="metric-bars-track">
                <span className="bar-sub-track">
                  <span className="bar-prev" style={{ width: `${prevPct}%` }} />
                </span>
                <span className="bar-sub-track">
                  <span
                    className={`bar-curr ${isUp ? "up" : isDown ? "down" : ""}`}
                    style={{ width: `${currPct}%` }}
                  />
                </span>
              </span>
              <span className={`metric-val curr ${isUp ? "val-up" : isDown ? "val-down" : ""}`}>
                {curr.value}{curr.unit === "%" ? "%" : ""}
              </span>
            </button>
          );
        })}
      </div>

      <div className="comparison-footer">
        <span>
          {isZh
            ? "指标锁定于此时刻的证据快照。有效控球分母排除死球中断时间。点击任意行即可在右侧抽屉展开确定性数学证明。"
            : "Metrics stay fixed at this evidence snapshot. Controlled possession denominator excludes dead-ball intervals. Select any row to inspect proof."}
        </span>
      </div>
    </section>
  );
}
