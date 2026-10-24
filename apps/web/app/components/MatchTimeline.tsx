"use client";

type Chapter = {
  id: string;
  at: number;
  title: string;
  question: string;
};

type Moment = {
  id: string;
  chapter_id?: string;
  at: number;
  badge: string;
  title: string;
  question: string;
  assertion: string;
  summary: string;
  priority: number;
};

type MatchTimelineProps = {
  currentSeconds: number;
  totalSeconds?: number;
  chapters: Chapter[];
  moments: Moment[];
  focus: string | null;
  busy: boolean;
  onFocusChapter: (chapterId: "A" | "B" | "C") => void;
  onFocusMoment: (id: string) => void;
};

const clock = (s: number) =>
  `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}`;

export function MatchTimeline({
  currentSeconds,
  totalSeconds = 720,
  chapters,
  moments,
  focus,
  busy,
  onFocusChapter,
  onFocusMoment,
}: MatchTimelineProps) {
  const progressPercent = Math.min(100, Math.max(0, (currentSeconds / totalSeconds) * 100));

  return (
    <section className="match-narrative-timeline" aria-label="Match timeline and key moments">
      <div className="timeline-track-wrap">
        <div className="timeline-track">
          <div
            className="timeline-progress"
            style={{ width: `${progressPercent}%` }}
          />
          <div
            className="timeline-playhead"
            style={{ left: `${progressPercent}%` }}
          >
            <span className="playhead-badge">{clock(currentSeconds)}</span>
          </div>

          {/* Markers on timeline */}
          {chapters.map((ch) => {
            const pos = (ch.at / totalSeconds) * 100;
            const isReached = currentSeconds >= ch.at;
            const isFocused = focus === ch.id;
            const glyph = ch.id === "C" ? "⚽" : ch.id === "B" ? "⚡" : "🔍";

            return (
              <button
                key={ch.id}
                type="button"
                className={`timeline-marker ${isReached ? "reached" : ""} ${isFocused ? "focused" : ""}`}
                style={{ left: `${Math.min(98.5, Math.max(1.5, pos))}%` }}
                onClick={() => onFocusChapter(ch.id as "A" | "B" | "C")}
                title={`Chapter ${ch.id} at ${clock(ch.at)}: ${ch.title}`}
              >
                <span className="marker-icon">{glyph}</span>
                <span className="marker-tooltip">{clock(ch.at)} Ch {ch.id}</span>
              </button>
            );
          })}
        </div>
      </div>

      {moments.length > 0 && <div className="detected-moments" aria-label="Automatically detected moments">
        {moments.map(moment => <button type="button" key={moment.id} disabled={busy} onClick={() => onFocusMoment(moment.id)}>
          <time>{clock(moment.at)}</time> {moment.badge} <span>Inspect →</span>
        </button>)}
      </div>}
      <div className="chapters-strip" role="navigation" aria-label="Focus Moments">
        {chapters.map((ch) => {
          const isFocused = focus === ch.id;
          const isPassed = currentSeconds >= ch.at;
          const icon = ch.id === "A" ? "🔍" : ch.id === "B" ? "⚡" : "⚽";
          const subtitle =
            ch.id === "A"
              ? "Possession Divergence"
              : ch.id === "B"
                ? "Turnover Shot Burst"
                : "Goal sequence & recap";

          return (
            <button
              key={ch.id}
              type="button"
              className={`chapter-card ${isFocused ? "active" : ""} ${isPassed ? "unlocked" : "upcoming"}`}
              onClick={() => onFocusChapter(ch.id as "A" | "B" | "C")}
              disabled={busy}
              aria-pressed={isFocused}
            >
              <div className="card-top">
                <span className="chapter-glyph">{icon}</span>
                <span className="chapter-tag">MOMENT {ch.id}</span>
                <span className="chapter-time">{clock(ch.at)}</span>
              </div>
              <h3 className="card-title">{ch.title}</h3>
              <p className="card-subtitle">{subtitle}</p>
              <div className="card-cta">
                <span>{isFocused ? "Focused replay" : "Focus Moment"}</span>
                <span className="arrow">↗</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
