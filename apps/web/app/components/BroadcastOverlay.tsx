"use client";

type BroadcastOverlayProps = {
  score: { H: number; N: number };
  clockText: string;
  fanText: string;
  verdict: string;
  asOf: number;
};

const formatClock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function BroadcastOverlay({
  score,
  fanText,
  verdict,
  asOf,
}: BroadcastOverlayProps) {
  return (
    <div className="broadcast-overlay-preview" role="complementary" aria-label="Broadcast TV Overlay Graphic">
      <div className="overlay-header">
        <span className="live-sim-badge">BROADCAST OVERLAY PREVIEW SYNTHETIC MATCH</span>
        <span className="as-of-badge">AS OF {formatClock(asOf)}</span>
      </div>

      <div className="broadcast-lower-third-strap">
        <div className="strap-scorebug">
          <div className="scorebug-team home">
            <span className="team-code">HFC</span>
            <span className="team-goals">{score.H}</span>
          </div>
          <span className="scorebug-divider">–</span>
          <div className="scorebug-team away">
            <span className="team-goals">{score.N}</span>
            <span className="team-code">NBU</span>
          </div>
        </div>

        <div className="strap-content">
          <div className="strap-tagline">
            <span className="tag-lens">MATCHLENS INSIGHT</span>
            <span className={`tag-verdict ${verdict}`}>
              {verdict === "qualify" ? "QUALIFIED FINDING" : "AGENT VERIFIED"}
            </span>
          </div>
          <p className="strap-prose">{fanText}</p>
        </div>
      </div>

      <div className="overlay-footnote">
        <span>Preview only Same approved claim and original analysis time. No video processing.</span>
      </div>
    </div>
  );
}
