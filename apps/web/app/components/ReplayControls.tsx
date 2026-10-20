"use client";

type ReplayControlsProps = {
  paused: boolean;
  speed: number;
  ended: boolean;
  focus: string | null;
  busy: boolean;
  onPlayPause: () => void;
  onRestart: () => void;
  onExitFocus: () => void;
  onSpeedChange: (speed: 1 | 6 | 30) => void;
};

export function ReplayControls({
  paused,
  speed,
  ended,
  focus,
  busy,
  onPlayPause,
  onRestart,
  onExitFocus,
  onSpeedChange,
}: ReplayControlsProps) {
  return (
    <div className="replay-toolbar" role="toolbar" aria-label="Match replay controls">
      <div className="toolbar-left">
        {focus ? (
          <button
            type="button"
            className="btn-exit-focus"
            onClick={onExitFocus}
            disabled={busy}
          >
            <span>Exit Focus</span>
            <span className="arrow-glyph">→</span>
          </button>
        ) : (
          <button
            type="button"
            className={`btn-play-pause ${paused ? "is-play" : "is-pause"}`}
            onClick={onPlayPause}
            disabled={busy || ended}
            aria-label={paused ? "Play match replay" : "Pause match replay"}
          >
            <span className="control-icon">{paused ? "▶" : "⏸"}</span>
            <span>{paused ? "Play Replay" : "Pause"}</span>
          </button>
        )}

        <button
          type="button"
          className="btn-restart"
          onClick={onRestart}
          disabled={busy}
          title="Restart match from 00:00"
        >
          <span>↺ Restart</span>
        </button>
      </div>

      <div className="toolbar-info">
        <span>
          {focus
            ? "Analysis is fixed at this moment. Exit Focus to continue replay."
            : `Automatic moment detection · ${Math.ceil(720 / speed)}-second replay at ${speed}×`}
        </span>
      </div>

      <div className="toolbar-right">
        <span className="speed-title">Replay Speed</span>
        <div className="speed-group" role="group" aria-label="Playback speed">
          {([1, 6, 30] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={`btn-speed ${speed === s ? "active" : ""}`}
              onClick={() => onSpeedChange(s)}
              disabled={busy}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
