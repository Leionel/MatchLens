"use client";

import React from "react";
import { Locale } from "../lib/i18n";

/**
 * A broadcast lower-third built from one gate-approved claim.
 *
 * It is a preview, not an export: the same claim, the same match time, the same
 * evidence references that the investigation returned. The provenance strip is
 * not decoration — a synthetic replay must never look like a live broadcast,
 * and historical provider data must not look like tonight's fixture.
 */
export type OverlayProvenance = "synthetic" | "provider_payload" | "provider_schema_excerpt";

export interface BroadcastOverlayProps {
  homeTeam: string;
  awayTeam: string;
  score: { H: number; N: number };
  asOf: number;
  headline: string;
  verdict: string;
  refs: string[];
  claimLevel?: number;
  provenance: OverlayProvenance;
  registered?: boolean;
  locale?: Locale;
}

const clock = (value: number) => {
  const safe = Math.max(0, Math.round(value));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
};

const code = (name: string) => {
  const words = (name || "").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "—";
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words
    .map((word) => word[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
};

const provenanceLabel = (kind: OverlayProvenance, isZh: boolean) => {
  if (kind === "provider_payload") {
    return isZh ? "历史真实赛事数据" : "HISTORICAL PROVIDER DATA";
  }
  if (kind === "provider_schema_excerpt") {
    return isZh ? "提供方格式样本" : "PROVIDER SCHEMA EXCERPT";
  }
  return isZh ? "合成模拟回放" : "SYNTHETIC SIMULATED REPLAY";
};

export function BroadcastOverlay({
  homeTeam,
  awayTeam,
  score,
  asOf,
  headline,
  verdict,
  refs,
  claimLevel,
  provenance,
  registered = false,
  locale = "zh",
}: BroadcastOverlayProps) {
  const isZh = locale === "zh";
  return (
    <section
      className="r6-overlay"
      data-testid="broadcast-overlay"
      data-provenance={provenance}
      aria-label={isZh ? "转播字幕预览" : "Broadcast lower-third preview"}
    >
      <div className="r6-overlay-strip">
        <span className="r6-overlay-badge">{provenanceLabel(provenance, isZh)}</span>
        <span className="r6-overlay-asof">
          {isZh ? "比赛时间" : "MATCH TIME"} {clock(asOf)}
        </span>
        <span className="r6-overlay-preview-tag">
          {isZh ? "预览 · 非播出信号" : "PREVIEW · NOT BROADCAST OUTPUT"}
        </span>
      </div>

      <div className="r6-overlay-strap">
        <div className="r6-overlay-scorebug">
          <span>{code(homeTeam)}</span>
          <b>
            {score.H} – {score.N}
          </b>
          <span>{code(awayTeam)}</span>
        </div>
        <div className="r6-overlay-copy">
          <p className="r6-overlay-headline">{headline}</p>
          <p className="r6-overlay-meta">
            <span className={`r6-overlay-verdict ${verdict}`}>{verdict}</span>
            {typeof claimLevel === "number" && <span>L{claimLevel}</span>}
            <span>{registered ? (isZh ? "已登记 Claim" : "registered claim") : isZh ? "未登记" : "not registered"}</span>
          </p>
        </div>
      </div>

      {refs.length > 0 && (
        <p className="r6-overlay-refs" data-testid="broadcast-overlay-refs">
          <span>{isZh ? "证据引用" : "Evidence refs"}</span>
          {refs.slice(0, 6).map((ref) => (
            <code key={ref}>{ref}</code>
          ))}
        </p>
      )}
    </section>
  );
}
