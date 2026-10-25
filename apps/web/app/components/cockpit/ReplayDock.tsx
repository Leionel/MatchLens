"use client";

import React, { useEffect, useRef, useState } from "react";
import { CockpitState } from "./types";
import { Locale } from "../../lib/i18n";

interface ReplayDockProps {
  state: CockpitState;
  busy: boolean;
  locale?: Locale;
  onSeek: (at: number) => void;
  onControl: (body: object) => void;
}

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
};

/**
 * Replay controls belong to the pages that actually read the timeline.
 *
 * The slider is a local draft while the thumb moves; only release (or a
 * keyboard commit) sends one seek. Dragging therefore cannot flood the server
 * with requests, and a late response cannot move the thumb backwards.
 */
export const ReplayDock: React.FC<ReplayDockProps> = ({
  state,
  busy,
  locale = "zh",
  onSeek,
  onControl,
}) => {
  const isZh = locale === "zh";
  const current = Math.max(0, Number(state.at ?? 0));
  const max = Math.max(1, Number(state.format_seconds || 720));
  const nominal = Math.max(1, Number(state.nominal_duration || state.coverage?.format_seconds || max));
  const [dragging, setDragging] = useState(false);
  const [draft, setDraft] = useState(current);
  const draftRef = useRef(current);
  // One pointer drag emits both touchend and pointerup in Chromium. Remembering
  // the last committed draft lets the second handler return without a seek.
  const committedRef = useRef<number | null>(null);

  useEffect(() => {
    if (!dragging) {
      setDraft(current);
      draftRef.current = current;
    }
  }, [current, dragging]);

  const value = dragging ? draft : current;
  const commit = (next: number) => {
    const bounded = Math.max(0, Math.min(max, Math.round(next)));
    setDragging(false);
    setDraft(bounded);
    draftRef.current = bounded;
    if (committedRef.current === bounded) return;
    committedRef.current = bounded;
    if (bounded !== current) onSeek(bounded);
  };

  return (
    <section className="r6-replay" aria-label={isZh ? "比赛回放控制" : "Match replay controls"} data-testid="replay-dock">
      <div className="r6-replay-lead">
        <button
          type="button"
          className="r6-play"
          disabled={busy || state.ended}
          onClick={() => onControl({ action: state.paused ? "play" : "pause" })}
          aria-label={state.paused ? (isZh ? "播放回放" : "Play replay") : isZh ? "暂停回放" : "Pause replay"}
          title={state.paused ? "Space" : "Space"}
        >
          {state.paused ? "▶" : "Ⅱ"}
        </button>
        <button
          type="button"
          className="r6-icon-button"
          disabled={busy}
          onClick={() => onControl({ action: "restart" })}
          aria-label={isZh ? "回到开球" : "Back to kick-off"}
        >
          ↺
        </button>
        <div className="r6-clock">
          <b>{clock(value)}</b>
          <span>/ {clock(max)}</span>
        </div>
      </div>

      <input
        className="r6-replay-range"
        type="range"
        min={0}
        max={max}
        step={1}
        value={value}
        disabled={max <= 1}
        data-testid="replay-slider"
        aria-label={isZh ? "回放时间轴" : "Replay timeline"}
        aria-valuetext={`${clock(value)} / ${clock(max)}`}
        onPointerDown={() => {
          committedRef.current = null;
          setDragging(true);
        }}
        onInput={(event) => {
          committedRef.current = null;
          draftRef.current = Number(event.currentTarget.value);
          setDragging(true);
          setDraft(draftRef.current);
        }}
        onPointerUp={() => commit(draftRef.current)}
        onTouchEnd={() => commit(draftRef.current)}
        onKeyUp={() => commit(draftRef.current)}
        onBlur={() => {
          if (dragging) commit(draftRef.current);
        }}
      />

      <div className="r6-replay-right">
        <div className="r6-speed" role="group" aria-label={isZh ? "播放速度" : "Playback speed"}>
          {([1, 6, 30] as const).map((speed) => (
            <button
              key={speed}
              type="button"
              className={state.speed === speed ? "active" : ""}
              disabled={busy}
              onClick={() => onControl({ action: "speed", speed })}
            >
              {speed}×
            </button>
          ))}
        </div>
        {max > nominal + 1 && (
          <span className="r6-replay-note" title={isZh ? "含补时/加时，回放终点为最后一条记录事件" : "Includes stoppage/extra time; replay ends at the last recorded event"}>
            {isZh ? `补时可回放至 ${clock(max)}` : `stoppage replay to ${clock(max)}`}
          </span>
        )}
      </div>
    </section>
  );
};
