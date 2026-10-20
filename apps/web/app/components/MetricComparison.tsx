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
  onInspect,
}: MetricComparisonProps) {
  const prevStart = Math.max(0, at - 360);
  const prevEnd = Math.max(0, at - 180);
  const currStart = prevEnd;
  const currEnd = at;

  const metrics = [
    "possession",
    "shots",
    "entries",
    "high_recoveries",
    "transition_shots",
  ];

  return (
    <section className="metric-comparison-card" aria-label="Window Metric Delta Comparison">
      <div className="comparison-header">
        <div className="header-title-wrap">
          <span className="comparison-tag">TACTICAL METRICS DELTA</span>
          <h3 className="comparison-title">3-Minute Window Comparison</h3>
        </div>
        <div className="comparison-windows">
          <span className="window-pill prev">{clock(prevStart)}–{clock(prevEnd)}</span>
          <span className="window-arrow">→</span>
          <span className="window-pill curr">{clock(currStart)}–{clock(currEnd)}</span>
        </div>
      </div>

      <div className="comparison-table">
        <div className="table-head">
          <span>METRIC</span>
          <span>PREVIOUS</span>
          <span className="col-bar">DELTA VISUALIZER</span>
          <span>CURRENT</span>
        </div>

        {metrics.map((m) => {
          const prev = receipts[`H.${m}.previous`];
          const curr = receipts[`H.${m}.current`];
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
        <span>Metrics stay fixed at this evidence snapshot. Select a row to inspect its calculation.</span>
      </div>
    </section>
  );
}
