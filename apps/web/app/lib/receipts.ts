import type { Receipt } from "../components/cockpit/types";

/**
 * A receipt is a measurement with an explicit window. The UI must never read
 * `value` without checking `status`, because an unobserved window stores
 * `value: null` on purpose and rendering it as `0` would publish a number
 * nobody measured.
 */
export type ReceiptRead = {
  id: string;
  value: number | null;
  status: string;
  start: number | null;
  end: number | null;
  definition: string | null;
  raw: Receipt | null;
};

export function readReceipt(
  receipts: Record<string, Receipt> | null | undefined,
  id: string,
): ReceiptRead {
  const receipt = receipts?.[id] ?? null;
  const rawValue = receipt?.value;
  const value = typeof rawValue === "number" && Number.isFinite(rawValue) ? rawValue : null;
  const status = receipt?.status ?? (value === null ? "unobserved" : "ok");
  // A receipt that exists but is not "ok" carries no measurement, whatever
  // number a legacy payload might still hold.
  const measured = status === "ok" && value !== null;
  return {
    id,
    value: measured ? value : null,
    status,
    start: typeof receipt?.start === "number" ? receipt.start : null,
    end: typeof receipt?.end === "number" ? receipt.end : null,
    definition: receipt?.definition ?? null,
    raw: receipt,
  };
}

/** A count rendered for humans: measured number, or an explicit unknown. */
export function countText(read: ReceiptRead, unknown = "—"): string {
  if (read.value === null) return unknown;
  return Number.isInteger(read.value) ? String(read.value) : read.value.toFixed(2);
}

export function percentText(read: ReceiptRead, unknown = "—"): string {
  if (read.value === null) return unknown;
  return `${read.value.toFixed(0)}%`;
}

/**
 * The window a receipt actually covers, in match seconds, phrased for a
 * tooltip. This is what stops a three-minute number from being read as a
 * match total.
 */
export function windowLabel(read: ReceiptRead, lang: "zh" | "en"): string {
  if (read.start === null || read.end === null) return "";
  const from = Math.round(read.start);
  const to = Math.round(read.end);
  return lang === "zh" ? `${from}s–${to}s 窗口` : `window ${from}s–${to}s`;
}

/**
 * Whole-match receipts are frozen at the snapshot clock, so the end bound is
 * the honest "up to here" rather than a nominal 90 minutes.
 */
export function matchWindowLabel(read: ReceiptRead, lang: "zh" | "en"): string {
  if (read.end === null) return lang === "zh" ? "全场" : "whole match";
  return lang === "zh" ? `开场至 ${Math.round(read.end)}s` : `kick-off to ${Math.round(read.end)}s`;
}
