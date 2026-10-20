"use client";

type AudienceSwitcherProps = {
  mode: "fan" | "analyst";
  onChange: (mode: "fan" | "analyst") => void;
};

export function AudienceSwitcher({ mode, onChange }: AudienceSwitcherProps) {
  return (
    <div className="audience-switcher" role="group" aria-label="Perspective switch">
      <button
        type="button"
        className={`switch-tab ${mode === "fan" ? "active" : ""}`}
        aria-pressed={mode === "fan"}
        onClick={() => onChange("fan")}
      >
        <span className="tab-glyph">⚡</span>
        <span className="tab-title">Fan View</span>
        <span className="tab-subtitle">Narrative & Punchline</span>
      </button>
      <button
        type="button"
        className={`switch-tab ${mode === "analyst" ? "active" : ""}`}
        aria-pressed={mode === "analyst"}
        onClick={() => onChange("analyst")}
      >
        <span className="tab-glyph">📊</span>
        <span className="tab-title">Analyst View</span>
        <span className="tab-subtitle">Metrics & Verification</span>
      </button>
    </div>
  );
}
