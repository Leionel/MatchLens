import type { FootballEvent } from "../components/cockpit/types";

/**
 * Two different questions, two different answers.
 *
 * `isDrawable` answers "can this event be drawn on the 105x68 pitch?". It needs
 * both endpoints, because a pass without a recorded end point has no line.
 *
 * `isDisplayable` answers "does this event carry an identity, a clock and a
 * kind that a human can read?". A goal with no coordinates is still a goal:
 * dropping it from the feed would delete a real recorded fact because of a
 * missing spatial field. Spatial drawing and event listing must never share a
 * predicate.
 *
 * `isLocatable` is the softer spatial question: at least one endpoint exists,
 * enough to place a marker even when no line can be drawn.
 */

const isPoint = (point: unknown): point is [number, number] =>
  Array.isArray(point) &&
  point.length === 2 &&
  Number.isFinite(point[0]) &&
  Number.isFinite(point[1]);

export function isLocatable(event: Pick<FootballEvent, "start" | "end"> | null | undefined): boolean {
  if (!event) return false;
  return isPoint(event.start) || isPoint(event.end);
}

export function isDrawable(event: Pick<FootballEvent, "start" | "end"> | null | undefined): boolean {
  if (!event) return false;
  return isPoint(event.start) && isPoint(event.end);
}

export function isDisplayable(
  event: Pick<FootballEvent, "id" | "t" | "kind"> | null | undefined,
): boolean {
  if (!event) return false;
  const hasId = typeof event.id === "string" && event.id.length > 0;
  const hasClock = typeof event.t === "number" && Number.isFinite(event.t) && event.t >= 0;
  const hasKind = typeof event.kind === "string" && event.kind.length > 0;
  return hasId && hasClock && hasKind;
}

/** Events the pitch may draw: displayable *and* fully located. */
export function drawableEvents(events: FootballEvent[] | null | undefined): FootballEvent[] {
  return (events || []).filter((event) => isDisplayable(event) && isDrawable(event));
}

/** Events the feed must list: every readable recorded event, located or not. */
export function displayableEvents(events: FootballEvent[] | null | undefined): FootballEvent[] {
  return (events || []).filter(isDisplayable);
}
