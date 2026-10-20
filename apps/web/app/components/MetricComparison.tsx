"use client";

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
  onInspect: (receiptId: string) => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

const labels: Record<string, string> = {
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
  onInspect,
}: MetricComparisonProps) {
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
          <span className="comparison-tag">TACTICAL METRICS DELTA · {teamLabel.toUpperCase()}</span>
          <h3 className="comparison-title">3-Minute Window Comparison ({teamLabel})</h3>
        </div>
        <div className="comparison-windows">
          <span className="window-pill prev" title={`Previous window: ${prevDuration}s duration`}>
            {clock(prevStart)}–{clock(prevEnd)} ({prevDuration}s)
          </span>
          <span className="window-arrow">→</span>
          <span className="window-pill curr" title={`Current window: ${currDuration}s duration`}>
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
          ⚠️ Early match stage (t &lt; 3m): insufficient sample for two distinct 180s comparison windows.
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
          ℹ️ Single baseline window active (00:00–03:00); previous window represents opening baseline.
        </div>
      )}

      <div className="comparison-table">
        <div className="table-head">
          <span>METRIC</span>
          <span>PREVIOUS</span>
          <span className="col-bar">DELTA VISUALIZER</span>
          <span>CURRENT</span>
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
              title={`Click to inspect ${labels[m]} evidence receipt`}
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
        <span>Metrics stay fixed at this evidence snapshot. Controlled possession denominator excludes dead-ball intervals. Select any row to inspect proof.</span>
      </div>
    </section>
  );
}
