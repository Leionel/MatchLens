"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CockpitState } from "./types";
import { Locale } from "../../lib/i18n";

type QueueClaim = {
  claim_id: string;
  assertion: string;
  statement: string;
  claim_level: number;
  gate_status: string;
  lifecycle_status: string;
  editorial_status: string;
  editorial_approver?: string | null;
  evidence_hash: string;
  dataset_revision?: string | null;
  published: boolean;
  current_revision_id?: string | null;
};

type RundownItem = {
  order: number;
  claim_id: string;
  revision_id?: string | null;
  statement: string;
  evidence_hash: string;
  valid?: boolean;
  reasons?: string[];
};

type RundownView = {
  match_id: string;
  snapshot_id: string;
  dataset_revision?: string | null;
  valid?: boolean;
  stale_items?: string[];
  items: RundownItem[];
};

type ManifestItem = {
  claim_id: string;
  revision_id?: string | null;
  evidence_hash?: string;
  dataset_revision?: string | null;
  gate_status?: string;
  editorial_status?: string;
  editorial_approver?: string | null;
  valid: boolean;
  reasons?: string[];
};

type ManifestHistoryEntry = {
  manifest_id: string;
  generated_at: number;
  generated_by?: string;
  valid: boolean;
  dataset_revision?: string | null;
  package_sha256?: string | null;
  stale_items?: string[];
  items: { claim_id: string; valid: boolean }[];
};

type ExportResult = {
  filename: string;
  payload: string;
  export_format: string;
  manifest?: {
    manifest_id: string;
    valid: boolean;
    dataset_revision?: string | null;
    generated_by?: string;
    package_sha256?: string | null;
    stale_items?: string[];
    items: ManifestItem[];
  };
};

interface ProducerWorkspaceProps {
  state: CockpitState;
  locale?: Locale;
}

const statusTone: Record<string, string> = {
  approved: "var(--text-emerald)",
  pending: "var(--text-gold)",
  rejected: "var(--red-11)",
  withdrawn: "var(--red-11)",
  qualified: "var(--text-gold)",
  current: "var(--text-emerald)",
};

export const ProducerWorkspace: React.FC<ProducerWorkspaceProps> = ({ state, locale = "zh" }) => {
  const isZh = locale === "zh";
  const [token, setToken] = useState("");
  const [queue, setQueue] = useState<QueueClaim[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [rundown, setRundown] = useState<RundownView | null>(null);
  const [exported, setExported] = useState<ExportResult | null>(null);
  const [manifestHistory, setManifestHistory] = useState<ManifestHistoryEntry[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [highlightClaimId, setHighlightClaimId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const matchId = state.match_id || "syn_default";
  // Disabled controls must say why: the reason doubles as the next step.
  const buildBlockReason = !token
    ? isZh ? "先输入制作人令牌" : "Enter the producer token first"
    : selected.length === 0
      ? isZh ? "先在左侧勾选可播条目" : "Tick broadcastable claims first"
      : rundown && rundown.valid === false
        ? isZh ? "Rundown 含失效项：回审后重建" : "Rundown has stale items: re-review and rebuild"
        : "";
  const exportBlockReason = !token
    ? buildBlockReason
    : !rundown
      ? isZh ? "先建立 Rundown" : "Build a rundown first"
      : rundown.valid === false
        ? isZh ? "Rundown 未通过读时校验" : "Rundown failed read-time validation"
        : "";
  const snapshotId = state.snapshot_id;

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("matchlens-producer-token");
      if (saved) setToken(saved);
    } catch {}
  }, []);

  const headers = useMemo(
    () => ({ "Content-Type": "application/json", "X-MatchLens-Token": token }),
    [token]
  );

  const loadQueue = useCallback(async () => {
    if (!token || !snapshotId) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(
        `/api/broadcast/queue/producer?match_id=${encodeURIComponent(matchId)}&snapshot_id=${encodeURIComponent(snapshotId)}`,
        { headers }
      );
      if (!res.ok) throw new Error(await res.text() || `Queue failed (${res.status})`);
      const data = await res.json();
      setQueue(data.records || []);
      setSelected((current) => {
        if (current.length) return current;
        return (data.records || [])
          .filter((claim: QueueClaim) => claim.published)
          .map((claim: QueueClaim) => claim.claim_id);
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [headers, matchId, snapshotId, token]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  const loadRundown = useCallback(async () => {
    if (!snapshotId) return null;
    const res = await fetch(
      `/api/broadcast/rundown?match_id=${encodeURIComponent(matchId)}&snapshot_id=${encodeURIComponent(snapshotId)}`
    );
    if (!res.ok) {
      setRundown(null);
      return null;
    }
    const data = await res.json();
    setRundown(data);
    return data as RundownView;
  }, [matchId, snapshotId]);

  // The persisted rundown is read back from the server on every snapshot
  // change, so an editor sees a rundown that a withdrawal has invalidated
  // instead of an empty panel.
  useEffect(() => {
    void loadRundown();
  }, [loadRundown]);

  const loadManifestHistory = useCallback(async () => {
    if (!token || !snapshotId) return;
    try {
      const res = await fetch(
        `/api/broadcast/manifests?match_id=${encodeURIComponent(matchId)}&snapshot_id=${encodeURIComponent(snapshotId)}`,
        { headers }
      );
      if (!res.ok) {
        setManifestHistory([]);
        return;
      }
      const data = await res.json();
      setManifestHistory(data.manifests || []);
    } catch {
      setManifestHistory([]);
    }
  }, [headers, matchId, snapshotId, token]);

  useEffect(() => {
    void loadManifestHistory();
  }, [loadManifestHistory]);

  const decide = async (claimId: string, decision: "approved" | "rejected") => {
    if (!snapshotId) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/story/editorial-approval", {
        method: "POST",
        headers,
        body: JSON.stringify({
          match_id: matchId,
          snapshot_id: snapshotId,
          claim_id: claimId,
          decision,
        }),
      });
      if (!res.ok) throw new Error(await res.text() || `Editorial action failed (${res.status})`);
      setNotice(isZh ? "编辑状态已更新。" : "Editorial state updated.");
      await loadQueue();
      // A withdrawal must not leave a previously valid rundown looking publishable.
      const checked = await loadRundown();
      if (checked && checked.valid === false) {
        setExported(null);
        setNotice(isZh ? "编辑状态已更新；Rundown 含失效项，需重新校验。" : "Editorial state updated; the rundown has stale items and must be rebuilt.");
      }
      setSelected((current) => current.filter((id) => id !== claimId || decision === "approved"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const buildRundown = async () => {
    if (!snapshotId || selected.length === 0) return;
    setBusy(true);
    setError("");
    setExported(null);
    try {
      const res = await fetch("/api/broadcast/rundown", {
        method: "POST",
        headers,
        body: JSON.stringify({ match_id: matchId, snapshot_id: snapshotId, claim_ids: selected }),
      });
      if (!res.ok) throw new Error(await res.text() || `Rundown failed (${res.status})`);
      await res.json();
      const checked = await loadRundown();
      setNotice(
        checked?.valid
          ? isZh ? "Rundown 已建立并完成读时校验。" : "Rundown built and revalidated at read time."
          : isZh ? "Rundown 已建立，但读时校验发现失效项。" : "Rundown built, but read-time validation found stale items."
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const moveSelected = (claimId: string, delta: number) => {
    setSelected((current) => {
      const from = current.indexOf(claimId);
      const to = from + delta;
      if (from < 0 || to < 0 || to >= current.length) return current;
      const next = [...current];
      next.splice(from, 1);
      next.splice(to, 0, claimId);
      return next;
    });
    setRundown(null);
    setExported(null);
  };

  const removeFromSelection = (claimId: string) => {
    setSelected((current) => current.filter((id) => id !== claimId));
    setRundown(null);
    setExported(null);
  };

  /** Jump a stale rundown item back into the review queue for re-review. */
  const reviewStaleClaim = (claimId: string) => {
    setHighlightClaimId(claimId);
    const row = document.querySelector(`[data-claim-id="${claimId}"]`);
    row?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => setHighlightClaimId(""), 2400);
  };

  const exportStory = async (format: "json" | "markdown" | "svg") => {
    if (!snapshotId) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/broadcast/export", {
        method: "POST",
        headers,
        body: JSON.stringify({
          match_id: matchId,
          snapshot_id: snapshotId,
          perspective: "media",
          export_format: format,
        }),
      });
      if (!res.ok) throw new Error(await res.text() || `Export failed (${res.status})`);
      const data: ExportResult = await res.json();
      setExported(data);
      const blob = new Blob([data.payload], {
        type: format === "json" ? "application/json" : format === "svg" ? "image/svg+xml" : "text/markdown",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = data.filename;
      link.click();
      URL.revokeObjectURL(url);
      setNotice(isZh ? "导出完成，Manifest 已生成并计入历史。" : "Export complete; the manifest was recorded in history.");
      await loadManifestHistory();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!snapshotId) {
    return (
      <div className="glass-panel" style={{ padding: 24, color: "var(--text-tertiary)", fontSize: 14 }}>
        {isZh ? "请先在比赛中暂停或定位到要发布的快照。" : "Pause or seek the match to select a publishable snapshot first."}
      </div>
    );
  }

  return (
    <div className="workspace-pane-fade" style={{ display: "grid", gap: 16 }}>
      <section className="glass-panel" style={{ padding: 18, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>
              {isZh ? "制作人工作区" : "Producer workspace"}
            </h2>
          </div>
          <label style={{ display: "grid", gap: 4, fontSize: 12, color: "var(--text-secondary)", minWidth: 260 }}>
            {isZh ? "制作人令牌" : "Producer token"}
            <input
              type="password"
              value={token}
              autoComplete="off"
              onChange={(e) => {
                setToken(e.target.value);
                try {
                  sessionStorage.setItem("matchlens-producer-token", e.target.value);
                } catch {}
              }}
              placeholder={isZh ? "仅保存在本标签页" : "Stored in this tab only"}
              style={{
                minHeight: 34,
                background: "var(--input-bg)",
                color: "var(--input-text)",
                border: "0.5px solid var(--pitch-border)",
                borderRadius: 6,
                padding: "4px 8px",
              }}
            />
          </label>
        </div>
        {error && <div role="alert" style={{ fontSize: 12, color: "var(--red-11)" }}>{error}</div>}
        {notice && <div role="status" style={{ fontSize: 12, color: "var(--text-emerald)" }}>{notice}</div>}
      </section>

      <div className="producer-grid" style={{ gap: 16 }}>
        <section className="glass-panel" style={{ padding: 16, display: "grid", gap: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
            <h3 style={{ fontSize: 14, fontWeight: 750, margin: 0 }}>
              {isZh ? "审核队列" : "Review queue"}
            </h3>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {queue.length} {isZh ? "条结论" : "claims"}
            </span>
          </div>
          {queue.length === 0 && (
            <div className="mz-enter-late" style={{ padding: "14px 16px", fontSize: 12, color: "var(--text-secondary)", display: "grid", gap: 10 }}>
              {token ? (
                <span>{isZh ? "当前快照没有注册结论。先在战报工作台发起调查并晋升结论，队列才会出现条目。" : "No registered claims for this snapshot. Promote an investigation first."}</span>
              ) : (
                <div className="mz-steps">
                  <div className="mz-step">{isZh ? "在上方输入制作人令牌（仅保存在本标签页）。" : "Enter the producer token above (stored in this tab only)."}</div>
                  <div className="mz-step">{isZh ? "审核 Gate 已通过的结论：批准或拒绝。" : "Review gate-approved claims: approve or reject."}</div>
                  <div className="mz-step">{isZh ? "把可播结论编排成 Rundown，预览后导出。" : "Order broadcastable claims into a rundown, preview and export."}</div>
                </div>
              )}
            </div>
          )}
          <div style={{ display: "grid", gap: 8 }}>
            {queue.map((claim) => {
              const checked = selected.includes(claim.claim_id);
              const publishable = claim.gate_status === "approved" && claim.editorial_status === "approved" && claim.lifecycle_status === "current";
              return (
                <div
                  key={claim.claim_id}
                  data-testid="producer-claim-row"
                  data-claim-id={claim.claim_id}
                  data-gate-status={claim.gate_status}
                  data-lifecycle-status={claim.lifecycle_status}
                  data-editorial-status={claim.editorial_status}
                  className={`mz-card mz-card-hover${checked ? " mz-claim-checked" : ""}${highlightClaimId === claim.claim_id ? " mz-claim-highlight" : ""}`}
                  style={{
                    display: "grid",
                    gap: 8,
                    padding: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
                    <b style={{ fontSize: 12 }}>{claim.assertion.replace(/_/g, " ")}</b>
                    <span style={{ fontSize: 12, color: statusTone[claim.lifecycle_status] || "var(--text-secondary)" }}>
                      {claim.lifecycle_status} / {claim.gate_status} / {claim.editorial_status}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{claim.statement}</p>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                    <label
                      style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12, color: "var(--text-secondary)" }}
                      title={
                        publishable
                          ? undefined
                          : isZh
                            ? `尚不可播：gate ${claim.gate_status} / 编辑 ${claim.editorial_status} / 生命周期 ${claim.lifecycle_status}`
                            : `Not broadcastable: gate ${claim.gate_status} / editorial ${claim.editorial_status} / lifecycle ${claim.lifecycle_status}`
                      }
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!publishable}
                        onChange={(e) =>
                          setSelected((current) =>
                            e.target.checked
                              ? [...current, claim.claim_id]
                              : current.filter((id) => id !== claim.claim_id)
                          )
                        }
                      />
                      {isZh ? "加入 Rundown" : "Add to rundown"}
                    </label>
                    <button
                      type="button"
                      disabled={busy || !token || claim.gate_status !== "approved" || claim.lifecycle_status !== "current"}
                      onClick={() => decide(claim.claim_id, "approved")}
                      className="mz-btn"
                    >
                      {isZh ? "批准" : "Approve"}
                    </button>
                    <button
                      type="button"
                      disabled={busy || !token}
                      onClick={() => decide(claim.claim_id, "rejected")}
                      className="mz-btn mz-btn-danger"
                    >
                      {isZh ? "拒绝" : "Reject"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="glass-panel" style={{ padding: 16, display: "grid", gap: 10, alignContent: "start" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
            <h3 style={{ fontSize: 14, fontWeight: 750, margin: 0 }}>
              {isZh ? "Rundown 与导出" : "Rundown and export"}
            </h3>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
              {rundown ? `${rundown.items.length} ${isZh ? "项" : "items"}` : isZh ? "未建立" : "Not built"}
            </span>
          </div>
          {selected.length > 0 && (
            <div style={{ display: "grid", gap: 6 }}>
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "baseline", gap: 8 }}>
                <button
                  type="button"
                  className="mz-btn"
                  data-testid="rundown-preview-toggle"
                  onClick={() => setShowPreview((v) => !v)}
                  style={{ minHeight: 26, padding: "0 8px" }}
                >
                  {showPreview ? (isZh ? "隐藏预览" : "Hide preview") : isZh ? "预览 Rundown" : "Preview rundown"}
                </button>
              </div>
              {showPreview && (
                <div
                  data-testid="rundown-preview"
                  style={{
                    display: "grid",
                    gap: 6,
                    padding: 10,
                    borderRadius: 6,
                    border: "0.5px dashed var(--glass-border)",
                    background: "color-mix(in srgb, var(--slate-1) 55%, transparent)",
                  }}
                >
                  <div style={{ fontSize: 11, color: "var(--text-gold)" }}>
                    {isZh
                      ? "预览仅基于当前队列投影，非服务器权威；以建立后的读时校验为准。"
                      : "Preview is built from the queue projection and is not server-authoritative; the read-time validation after building decides."}
                  </div>
                  {selected.map((claimId, index) => {
                    const claim = queue.find((c) => c.claim_id === claimId);
                    const ready = claim && claim.gate_status === "approved" && claim.editorial_status === "approved" && claim.lifecycle_status === "current";
                    return (
                      <div key={claimId} style={{ display: "grid", gap: 2, fontSize: 12 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                          <b style={{ fontFamily: "var(--font-mono)" }}>{index + 1}</b>
                          <span style={{ color: "var(--text-primary)", fontWeight: 650 }}>
                            {(claim?.assertion || claimId).replace(/_/g, " ")}
                          </span>
                          <span style={{ color: ready ? "var(--text-emerald)" : "var(--red-11)", marginLeft: "auto" }}>
                            {ready ? (isZh ? "可播" : "broadcastable") : (isZh ? "尚不可播" : "not broadcastable")}
                          </span>
                        </div>
                        {claim && (
                          <span style={{ color: "var(--text-secondary)", lineHeight: 1.5, paddingLeft: 22 }}>
                            {claim.statement}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {selected.map((claimId, index) => {
                const claim = queue.find((c) => c.claim_id === claimId);
                return (
                  <div
                    key={claimId}
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: 12,
                      padding: "6px 8px",
                      borderRadius: 6,
                      border: "0.5px solid var(--glass-border)",
                    }}
                  >
                    <span style={{ display: "flex", gap: 8, alignItems: "center", minWidth: 0 }}>
                      <span className="mz-cue">{index + 1}</span>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {(claim?.assertion || claimId).replace(/_/g, " ")}
                      </span>
                    </span>
                    <span style={{ display: "flex", gap: 4 }}>
                      <button
                        type="button"
                        aria-label={isZh ? `上移 ${claimId}` : `Move ${claimId} up`}
                        disabled={busy || index === 0}
                        onClick={() => moveSelected(claimId, -1)}
                        className="mz-btn"
                        style={{ minHeight: 26, padding: "0 8px" }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        aria-label={isZh ? `下移 ${claimId}` : `Move ${claimId} down`}
                        disabled={busy || index === selected.length - 1}
                        onClick={() => moveSelected(claimId, 1)}
                        className="mz-btn"
                        style={{ minHeight: 26, padding: "0 8px" }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        aria-label={isZh ? `移出 ${claimId}` : `Remove ${claimId}`}
                        disabled={busy}
                        onClick={() => removeFromSelection(claimId)}
                        className="mz-btn mz-btn-danger"
                        style={{ minHeight: 26, padding: "0 8px" }}
                      >
                        ✕
                      </button>
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              className="mz-btn mz-btn-primary"
              disabled={busy || !token || selected.length === 0}
              onClick={buildRundown}
              title={buildBlockReason || undefined}
            >
              {isZh ? "建立并校验 Rundown" : "Build and validate rundown"}
            </button>
            <span style={{ width: 1, height: 22, background: "var(--glass-border)" }} aria-hidden="true" />
            {(["json", "markdown", "svg"] as const).map((format) => (
              <button
                key={format}
                type="button"
                className="mz-btn"
                disabled={busy || !token || !rundown?.valid}
                onClick={() => exportStory(format)}
                title={exportBlockReason || undefined}
              >
                {format.toUpperCase()}
              </button>
            ))}
            {buildBlockReason && (
              <span data-testid="producer-block-reason" style={{ fontSize: 11, color: "var(--text-gold)" }}>
                {buildBlockReason}
              </span>
            )}
          </div>

          {rundown && (
            <div style={{ display: "grid", gap: 8 }}>
              <div style={{ fontSize: 12, color: rundown.valid ? "var(--text-emerald)" : "var(--red-11)" }}>
                {rundown.valid
                  ? isZh ? "当前 Rundown 全部有效" : "All rundown items are valid"
                  : isZh ? `存在失效项: ${(rundown.stale_items || []).join(", ")}` : `Stale items: ${(rundown.stale_items || []).join(", ")}`}
              </div>
              {rundown.items.map((item) => (
                <div key={`${item.order}-${item.claim_id}`} style={{ padding: 10, borderRadius: 6, border: "0.5px solid var(--glass-border)", display: "grid", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 12 }}>
                    <b>#{item.order} {item.claim_id}</b>
                    <span style={{ color: item.valid === false ? "var(--red-11)" : "var(--text-emerald)" }}>
                      {item.valid === false ? (isZh ? "失效" : "stale") : isZh ? "有效" : "valid"}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>{item.statement}</div>
                  {item.reasons && item.reasons.length > 0 && (
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ fontSize: 12, color: "var(--red-11)" }}>{item.reasons.join(", ")}</span>
                      <button
                        type="button"
                        data-testid={`rereview-${item.claim_id}`}
                        onClick={() => reviewStaleClaim(item.claim_id)}
                        className="mz-btn"
                        style={{ minHeight: 24, fontSize: 11, padding: "0 8px" }}
                      >
                        {isZh ? "回审该结论" : "Re-review claim"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {exported?.manifest && (
            <div style={{ display: "grid", gap: 8, padding: 10, borderRadius: 6, border: "0.5px solid var(--glass-border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
                <span style={{ fontSize: 12, fontWeight: 750 }}>{isZh ? "导出 Manifest" : "Export manifest"}</span>
                <span style={{ fontSize: 12, color: exported.manifest.valid ? "var(--text-emerald)" : "var(--red-11)" }}>
                  {exported.manifest.valid ? (isZh ? "有效" : "valid") : (isZh ? "无效" : "invalid")}
                </span>
              </div>
              <div style={{ display: "grid", gap: 2, fontSize: 12, color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
                <span>{exported.manifest.manifest_id}</span>
                <span>{(exported.manifest.package_sha256 || "").slice(0, 16) || "—"}</span>
              </div>
              <div style={{ display: "grid", gap: 2, fontSize: 12, color: "var(--text-secondary)" }}>
                <span>
                  {isZh ? "数据集版本" : "Dataset revision"}:{" "}
                  <span style={{ fontFamily: "var(--font-mono)" }}>{exported.manifest.dataset_revision || "—"}</span>
                </span>
                <span>
                  {isZh ? "导出身份" : "Generated by"}: {exported.manifest.generated_by || "—"}
                </span>
              </div>
              {exported.manifest.items.map((item) => (
                <div
                  key={item.claim_id}
                  style={{
                    display: "grid",
                    gap: 2,
                    paddingTop: 6,
                    borderTop: "0.5px solid var(--glass-border)",
                    fontSize: 12,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <b style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.claim_id}</b>
                    <span style={{ color: item.valid ? "var(--text-emerald)" : "var(--red-11)" }}>
                      {item.valid ? (isZh ? "可播" : "broadcastable") : (isZh ? "已失效" : "stale")}
                    </span>
                  </div>
                  <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-tertiary)", overflowWrap: "anywhere" }}>
                    rev {item.revision_id ? `${item.revision_id.slice(0, 12)}…` : "—"} · ev {item.evidence_hash ? `${item.evidence_hash.slice(0, 12)}…` : "—"}
                  </div>
                  <div>
                    {isZh ? "审批人" : "Approver"}: {item.editorial_approver || "—"} · {item.gate_status} / {item.editorial_status}
                  </div>
                  {item.reasons && item.reasons.length > 0 && (
                    <div style={{ color: "var(--red-11)" }}>{item.reasons.join(", ")}</div>
                  )}
                </div>
              ))}
              {exported.manifest.stale_items && exported.manifest.stale_items.length > 0 && (
                <div style={{ fontSize: 12, color: "var(--red-11)" }}>
                  {isZh ? `失效项: ${exported.manifest.stale_items.join(", ")}` : `Stale: ${exported.manifest.stale_items.join(", ")}`}
                </div>
              )}
            </div>
          )}

          {manifestHistory.length > 0 && (
            <details style={{ borderTop: "0.5px solid var(--glass-border)", paddingTop: 8 }} data-testid="manifest-history">
              <summary className="mz-summary" style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                {isZh ? `Manifest 历史（${manifestHistory.length}）` : `Manifest history (${manifestHistory.length})`}
              </summary>
              <div className="mz-timeline" style={{ marginTop: 10 }}>
                {manifestHistory.map((m) => (
                  <div
                    key={`${m.manifest_id}-${m.generated_at}`}
                    className="mz-timeline-item"
                    style={{ display: "grid", gap: 2, fontSize: 12 }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <span style={{ fontFamily: "var(--font-mono)", overflowWrap: "anywhere" }}>{m.manifest_id}</span>
                      <span style={{ color: m.valid ? "var(--text-emerald)" : "var(--red-11)" }}>
                        {m.valid ? (isZh ? "有效" : "valid") : (isZh ? "无效" : "invalid")}
                      </span>
                    </div>
                    <div style={{ color: "var(--text-tertiary)", display: "flex", gap: 10, flexWrap: "wrap" }}>
                      <span>{new Date(m.generated_at * 1000).toLocaleString()}</span>
                      <span>{isZh ? "导出人" : "by"}: {m.generated_by || "—"}</span>
                      <span>{(m.items || []).length} {isZh ? "项" : "items"}</span>
                      {(m.stale_items || []).length > 0 && (
                        <span style={{ color: "var(--text-gold)" }}>
                          {isZh ? "失效" : "stale"}: {m.stale_items!.join(", ")}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>
      </div>
    </div>
  );
};
