"use client";

export type HighlightCandidate = {
  highlight_id: string;
  title: string;
  team: string;
  start_t: number;
  end_t: number;
  peak_t: number;
  impact_score: number;
  category: "goal" | "shot" | "oaai_surge" | string;
  associated_sequence_ids: string[];
  key_event_ids: string[];
  claim_level: number;
  description: string;
};

interface HighlightLocatorProps {
  highlights?: HighlightCandidate[] | null;
  onSelectHighlight?: (highlight: HighlightCandidate) => void;
  selectedHighlightId?: string | null;
  homeTeamName?: string;
  awayTeamName?: string;
}

export function HighlightLocator({
  highlights,
  onSelectHighlight,
  selectedHighlightId,
  homeTeamName = "Harbor FC",
  awayTeamName = "Northbridge United",
}: HighlightLocatorProps) {
  if (!highlights || highlights.length === 0) {
    return (
      <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 text-slate-400">
        正在基于 OAAI 变化点及 S2 序列扫描核心攻防高光波次...
      </div>
    );
  }

  return (
    <div className="bg-[#151e2e] border border-[rgba(255,255,255,0.09)] rounded-xl p-5 shadow-lg space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[rgba(255,255,255,0.08)] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-[#00b074]/20 text-[#00b074] border border-[#00b074]/30">
              BL-12 · Highlight Locator
            </span>
            <span className="text-[10px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
              波次联动索引
            </span>
            <h3 className="text-base font-bold text-white tracking-wide">
              Highlight Locator (核心攻防波次定位)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            与 OAAI 变化点检测及 S2 控球序列联动，自动定位比赛关键攻防高光与胜负波次。
          </p>
        </div>
      </div>

      {/* Highlights List */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {highlights.map((hl) => {
          const isSelected = selectedHighlightId === hl.highlight_id;
          const isGoal = hl.category === "goal";
          const isShot = hl.category === "shot";
          const isHome = hl.team === "H";
          const teamLabel = isHome ? homeTeamName : awayTeamName;

          let badgeColor = "bg-blue-500/20 text-blue-300 border-blue-500/40";
          if (isGoal) badgeColor = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
          if (isShot) badgeColor = "bg-amber-500/20 text-amber-300 border-amber-500/40";

          return (
            <div
              key={hl.highlight_id}
              onClick={() => onSelectHighlight?.(hl)}
              className={`p-3.5 rounded-xl border ${
                isSelected
                  ? "border-[#00e599] bg-[#091f1a] ring-1 ring-[#00e599]"
                  : "border-[rgba(255,255,255,0.08)] bg-[#0e1420] hover:border-[#00b074]/60"
              } cursor-pointer transition-all space-y-2.5 flex flex-col justify-between`}
            >
              <div>
                <div className="flex items-center justify-between gap-1">
                  <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${badgeColor}`}>
                    {hl.category.toUpperCase()}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-slate-400 font-mono">
                      {Math.floor(hl.start_t / 60)}' - {Math.floor(hl.end_t / 60)}'
                    </span>
                    <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-bold">
                      ★ {hl.impact_score.toFixed(1)}
                    </span>
                  </div>
                </div>

                <h4 className="text-sm font-bold text-white mt-1 line-clamp-1">{hl.title}</h4>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                  {hl.description}
                </p>
              </div>

              <div className="border-t border-[rgba(255,255,255,0.06)] pt-2 flex items-center justify-between text-xs">
                <span className="text-slate-400">
                  主导: <b className={isHome ? "text-[#00e599]" : "text-amber-400"}>{teamLabel}</b>
                </span>
                <span className="text-[10px] text-[#00b074] hover:underline flex items-center gap-0.5 font-semibold">
                  定位波次 →
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
