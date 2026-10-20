"use client";

import { useEffect, useRef } from "react";

type FootballEvent = {
  id: string;
  seq: number;
  t: number;
  kind: string;
  team: "H" | "N";
  actor: string;
  receiver: string | null;
  start: [number, number];
  end: [number, number];
  outcome: string;
  possession_id: number;
};

type Receipt = {
  id: string;
  value: number;
  unit: string;
  event_ids: string[];
  definition: string;
  start: number;
  end: number;
  numerator?: number;
  denominator?: number;
  chains?: { event_ids: string[]; seconds: number }[] | string[][];
};

type Evidence = {
  snapshot_id: string;
  as_of: number;
  events: FootballEvent[];
  receipts: Record<string, Receipt>;
  limitations: string[];
};

type EvidenceDrawerProps = {
  isOpen: boolean;
  evidence: Evidence | null;
  receiptId: string;
  selectedEventId: string;
  showAllEvents: boolean;
  players: Record<string, Record<string, string>>;
  onClose: () => void;
  onSelectReceipt: (receiptId: string) => void;
  onSelectEvent: (eventId: string) => void;
  onToggleShowAll: () => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

const labels: Record<string, string> = {
  possession: "Controlled Possession",
  shots: "Shot Attempts",
  entries: "Attacking Entries (x=70m)",
  high_recoveries: "High Ball Recoveries",
  transition_shots: "Recovery → Shot Chains",
  goals: "Breakthrough Goals",
};

const titleFor = (id: string) => {
  const parts = id.split(".");
  const name = labels[parts[1]] || parts[1];
  const windowName = parts[2] ? ` (${parts[2].toUpperCase()})` : "";
  return `${name}${windowName}`;
};

export function EvidenceDrawer({
  isOpen,
  evidence,
  receiptId,
  selectedEventId,
  showAllEvents,
  players,
  onClose,
  onSelectReceipt,
  onSelectEvent,
  onToggleShowAll,
}: EvidenceDrawerProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!isOpen || !evidence) return;
    const opener = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    dialog?.showModal();
    document.body.style.overflow = "hidden";
    headingRef.current?.focus({ preventScroll: true });
    return () => {
      dialog?.close();
      document.body.style.overflow = previousOverflow;
      opener?.focus({ preventScroll: true });
    };
  }, [isOpen]);

  if (!isOpen || !evidence) return null;

  const receipt = evidence.receipts[receiptId] || Object.values(evidence.receipts)[0];
  const selectedEvent =
    evidence.events.find((e) => e.id === selectedEventId) || evidence.events.at(-1) || null;

  return (
    <dialog ref={dialogRef} className="evidence-drawer-backdrop" aria-labelledby="evidence-drawer-title" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }} onCancel={(e) => { e.preventDefault(); onClose(); }} onKeyDown={(e) => {
      if (e.key !== "Tab") return;
      const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled),summary,a[href],[tabindex="0"]')).filter(item => item.getClientRects().length > 0);
      const first = items[0], last = items.at(-1);
      if (e.shiftKey && (document.activeElement === first || document.activeElement === headingRef.current)) {
        e.preventDefault(); last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first?.focus();
      }
    }}>
      <div
        className="evidence-drawer-panel"
        onClick={(e) => e.stopPropagation()}
        aria-label="Evidence & Verification Audit Drawer"
      >
        <div className="drawer-header">
          <div className="drawer-title-group">
            <span className="drawer-badge">AUDIT TRAIL & DETERMINISTIC PROOF</span>
            <h2 id="evidence-drawer-title" ref={headingRef} tabIndex={-1} className="drawer-heading">
              Evidence Receipts & Grounding
            </h2>
          </div>
          <div className="drawer-header-actions">
            <span className="snapshot-tag" title={evidence.snapshot_id}>
              Snapshot: <code>{evidence.snapshot_id.slice(0, 14)}...</code>
            </span>
            <button
              type="button"
              className="btn-close-drawer"
              onClick={onClose}
              aria-label="Close evidence panel"
            >
              ✕ Close
            </button>
          </div>
        </div>

        <div className="drawer-content-grid">
          {/* Left Column: Metric Receipts */}
          <div className="drawer-receipts-column">
            <div className="receipt-selector-group">
              <label htmlFor="receipt-select" className="receipt-select-label">
                Select Metric Receipt
              </label>
              <select
                id="receipt-select"
                value={receipt?.id || ""}
                onChange={(e) => onSelectReceipt(e.target.value)}
                className="receipt-dropdown"
              >
                {Object.values(evidence.receipts)
                  .filter((r) => r.id.startsWith("H."))
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {titleFor(r.id)}
                    </option>
                  ))}
              </select>
            </div>

            {receipt && (
              <div className="receipt-details-card">
                <div className="receipt-hero-stat">
                  <span className="stat-value">
                    {receipt.value}
                    {receipt.unit === "%" ? "%" : ""}
                  </span>
                  <div className="stat-meta">
                    <span className="stat-unit">
                      {receipt.unit === "%" ? "Controlled Time" : receipt.unit}
                    </span>
                    <span className="stat-window">
                      Window: {clock(receipt.start)}–{clock(receipt.end)}
                    </span>
                  </div>
                </div>

                <div className="receipt-formula-box">
                  <span className="formula-tag">DETERMINISTIC REDUCER FORMULA</span>
                  <p className="formula-desc">{receipt.definition}</p>
                  {receipt.denominator != null && (
                    <div className="formula-math">
                      <code>
                        {receipt.numerator}s / {receipt.denominator}s × 100 = {receipt.value}%
                      </code>
                    </div>
                  )}
                </div>

                {/* Event chains (Goal or Transition) */}
                {Boolean(receipt.chains?.length) && (
                  <div className="event-chains-box">
                    <span className="chains-title">Recorded On-Ball Event Chains</span>
                    <div className="chains-list">
                      {receipt.chains?.map((chain, idx) => {
                        const ids = Array.isArray(chain) ? chain : chain.event_ids;
                        const duration = Array.isArray(chain) ? null : chain.seconds;
                        return (
                          <button
                            key={idx}
                            type="button"
                            className="chain-button"
                            onClick={() => onSelectEvent(ids.at(-1) || "")}
                          >
                            <span className="chain-glyph">🔗</span>
                            <span>
                              {Array.isArray(chain)
                                ? `${chain.length}-event build-up ending with goal`
                                : `${ids.join(" → ")} (${duration}s transition)`}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Event IDs chip list */}
                <div className="event-chips-section">
                  <span className="chips-title">
                    Source Events ({receipt.event_ids.length} On-Ball Actions)
                  </span>
                  <div className="chips-wrap" role="group" aria-label="Source event identifiers">
                    {receipt.event_ids
                      .slice(0, showAllEvents ? undefined : 16)
                      .map((id) => (
                        <button
                          key={id}
                          type="button"
                          className={`event-id-chip ${id === selectedEventId ? "active" : ""}`}
                          onClick={() => onSelectEvent(id)}
                        >
                          {id}
                        </button>
                      ))}
                  </div>
                  {receipt.event_ids.length > 16 && (
                    <button
                      type="button"
                      className="btn-toggle-all-events"
                      onClick={onToggleShowAll}
                    >
                      {showAllEvents
                        ? "Show fewer events"
                        : `Show all ${receipt.event_ids.length} events`}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Telemetry & Event Inspector */}
          <div className="drawer-telemetry-column">
            <h3 className="telemetry-title">Event Telemetry Inspector</h3>

            {selectedEvent ? (
              <div className="telemetry-card">
                <div className="event-id-banner">
                  <span className="event-seq-id">{selectedEvent.id}</span>
                  <span className="event-time-pill">{clock(selectedEvent.t)}</span>
                  <span className={`event-kind-pill ${selectedEvent.kind}`}>
                    {selectedEvent.kind.toUpperCase()}
                  </span>
                </div>

                <div className="telemetry-grid">
                  <div className="tel-row">
                    <span className="tel-label">Player / Team:</span>
                    <span className="tel-value">
                      {players[selectedEvent.team]?.[selectedEvent.actor] || selectedEvent.actor}{" "}
                      <small>({selectedEvent.team === "H" ? "Harbor FC" : "Northbridge Utd"})</small>
                    </span>
                  </div>
                  {selectedEvent.receiver && (
                    <div className="tel-row">
                      <span className="tel-label">Receiver:</span>
                      <span className="tel-value">
                        {players[selectedEvent.team]?.[selectedEvent.receiver] || selectedEvent.receiver}
                      </span>
                    </div>
                  )}
                  <div className="tel-row">
                    <span className="tel-label">Start Coords:</span>
                    <span className="tel-value">
                      <code>({selectedEvent.start[0]}, {selectedEvent.start[1]}) m</code>
                    </span>
                  </div>
                  <div className="tel-row">
                    <span className="tel-label">End Coords:</span>
                    <span className="tel-value">
                      <code>({selectedEvent.end[0]}, {selectedEvent.end[1]}) m</code>
                    </span>
                  </div>
                  <div className="tel-row">
                    <span className="tel-label">Outcome:</span>
                    <span className={`tel-value outcome-${selectedEvent.outcome}`}>
                      {selectedEvent.outcome.toUpperCase()}
                    </span>
                  </div>
                  <div className="tel-row">
                    <span className="tel-label">Possession after event:</span>
                    <span className="tel-value">#{selectedEvent.possession_id}</span>
                  </div>
                </div>

                <details className="raw-json-details">
                  <summary>View Raw Event Payload</summary>
                  <pre className="raw-json-pre">
                    {JSON.stringify(selectedEvent, null, 2)}
                  </pre>
                </details>
              </div>
            ) : (
              <p className="no-event-selected">
                Click any Event ID chip to inspect its exact spatial coordinates.
              </p>
            )}

            {/* Prefix Events Scrubber */}
            <details className="prefix-scrubber-details">
              <summary>
                Browse All {evidence.events.length} Events in Snapshot Prefix
              </summary>
              <div className="prefix-scrubber-list">
                {evidence.events.map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    className={`prefix-event-btn ${e.id === selectedEventId ? "active" : ""}`}
                    onClick={() => onSelectEvent(e.id)}
                  >
                    <span className="p-id">{e.id}</span>
                    <span className="p-time">{clock(e.t)}</span>
                    <span className="p-team">{e.team}</span>
                    <span className="p-kind">{e.kind}</span>
                  </button>
                ))}
              </div>
            </details>
          </div>
        </div>
      </div>
    </dialog>
  );
}
