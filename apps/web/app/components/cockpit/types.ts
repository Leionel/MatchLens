export type WorkspaceId =
  | "match_hub"
  | "match_center"
  | "tactical_lab"
  | "story_agent"
  | "producer"
  | "validation_lab";

export type InvestigationSeed = {
  requestId: string;
  matchId: string;
  team: "H" | "N";
  at: number;
  focusType:
    | "moment"
    | "oaai_point"
    | "event"
    | "metric"
    | "sequence"
    | "player"
    | "zone"
    | "chart"
    | "shot_location"
    | "cross_match_diff";
  focusId: string | null;
  compareMatchIds?: string[];
  question?: string;
};

export type PerspectiveId = "coach" | "media" | "fan";

export type FootballEvent = {
  id: string;
  seq: number;
  t: number;
  kind: string;
  team: "H" | "N";
  actor: string;
  actor_name?: string;
  receiver: string | null;
  receiver_name?: string | null;
  start: [number, number] | null;
  end: [number, number] | null;
  located?: boolean;
  coordinate_frame?: "fixed" | "team_relative";
  outcome: string;
  possession_id: number;
  gain_m?: number | null;
  xt_value?: number;
  /** The period of play the provider annotated on the event. */
  period?: number;
  /** The provider's own minute label for the event. */
  provider_minute?: number;
};

export type Receipt = {
  id: string;
  value: number | null;
  status?: "ok" | "unobserved" | "not_applicable" | "missing_input";
  unit: string;
  event_ids: string[];
  definition: string;
  start: number;
  end: number;
  numerator?: number;
  denominator?: number;
  chains?: { event_ids: string[]; seconds: number }[] | string[][];
};

export type Card = {
  claim_id: string;
  assertion: string;
  verdict: string;
  fan: string;
  analyst: string;
  refs: string[];
  scope: string;
  reason: string;
  limitations: string[];
  snapshot_id: string;
  as_of: number;
  claim_level?: number;
  assumptions?: string[];
  verification_method?: string;
  counterevidence_checked?: boolean;
  gate_status?: "approved" | "disputed" | "rejected";
  gate_version?: string;
  gate_violations?: string[];
  editorial_status?: "pending" | "approved" | "rejected";
  editorial_approver?: string | null;
  evidence_hash?: string;
  source_run?: string;
  published?: boolean;
};

export type Audit = {
  type: string;
  role?: string;
  name?: string;
  from?: string;
  to?: string;
  status?: number;
  request_id?: number;
  usage?: { prompt_tokens: number; completion_tokens: number };
  [key: string]: unknown;
};

export type Result = {
  status: string;
  origin: string;
  accepted: Card[];
  rejected: {
    claim_id: string;
    reason: string;
    gate: string;
    verdict: string;
  }[];
  error?: string;
  duration_ms?: number;
  requests: number;
  audit: Audit[];
  snapshot_id: string;
  as_of: number;
  run_id: string;
  reused?: boolean;
};

export type Evidence = {
  snapshot_id: string;
  as_of: number;
  events: FootballEvent[];
  total_event_count?: number;
  provider_data_boundary?: {
    access_tier: string;
    state_window?: { window_seconds: number; total_events_observed: number } | null;
  } | null;
  receipts: Record<string, Receipt>;
  limitations: string[];
};

export type Moment = {
  id: string;
  team?: "H" | "N";
  chapter_id?: string;
  at: number;
  badge: string;
  title: string;
  question: string;
  assertion: string;
  summary: string;
  priority: number;
};

export type ScenarioMeta = {
  id: string;
  label: string;
  archetype: string;
  description: string;
};

export type PossessionSequence = {
  sequence_id: string;
  possession_id: number;
  team: "H" | "N";
  start_t: number;
  end_t: number;
  duration: number;
  origin_kind: string;
  pass_count: number;
  progressive_distance: number;
  territory_gained?: number;
  start_coords?: [number, number];
  end_coords?: [number, number];
  entered_final_third: boolean;
  outcome: string;
  players: string[];
  event_ids: string[];
  events_detail?: {
    seq_step: number;
    id: string;
    kind: string;
    team: "H" | "N";
    actor: string;
    actor_name?: string;
    receiver?: string | null;
    receiver_name?: string | null;
    start: [number, number];
    end: [number, number];
    outcome: string;
    t: number;
    gain_m: number;
    xt_value?: number;
    channel?: string;
  }[];
};

export type PlayerSpotlight = {
  player_id: string;
  name: string;
  team: "H" | "N";
  team_name: string;
  passes: number;
  progressive_passes: number;
  progressive_distance: number;
  final_third_entries: number;
  recoveries: number;
  shots: number;
  goals: number;
  touches?: number;
  sequences_involved: number;
  touch_points?: [number, number][];
  progressive_pass_ids?: string[];
  recovery_ids?: string[];
  event_ids: string[];
};

export type CockpitState = {
  revision: number;
  epoch: number;
  at: number;
  scenario?: string;
  scenarios?: ScenarioMeta[];
  focus_team?: "H" | "N";
  teams?: { H?: string; N?: string };
  match_context?: any;
  score: { H: number; N: number };
  score_basis?: "observed_prefix" | "official_final";
  official_score?: { H: number | null; N: number | null } | null;
  completeness?: {
    status: string;
    confidence?: number;
    known_missing_segments?: string[];
    coverage_by_period?: any[];
  } | null;
  provider_data_boundary?: {
    access_tier: string;
    state_window?: {
      start: number;
      end: number;
      window_seconds: number;
      events_in_window: number;
      events_returned: number;
      events_truncated: number;
      total_events_observed: number;
    } | null;
    full_event_access?: string;
    [key: string]: unknown;
  } | null;
  nominal_duration?: number;
  coverage?: {
    format_seconds: number;
    observed_start: number | null;
    observed_end: number | null;
    controlled_seconds: number;
    unobserved_seconds: number;
    continuous: boolean;
    time_coverage: number;
    event_coverage: number | null;
    event_coverage_status: "complete" | "unknown";
    event_count: number;
    score_status: string;
  };
  paused: boolean;
  speed: number;
  focus: string | null;
  ball: [number, number] | null;
  events: FootballEvent[];
  receipts: Record<string, Receipt>;
  sequences?: PossessionSequence[];
  tactical?: any;
  player_spotlight?: PlayerSpotlight[];
  players: Record<string, Record<string, string>>;
  chapters: { id: string; at: number; title: string; question: string }[];
  moments?: Moment[];
  active_moment?: Moment | null;
  snapshot_id: string | null;
  snapshot_as_of: number | null;
  analysis_receipts: Record<string, Receipt> | null;
  auto_status: string;
  analysis: { status: string; as_of: number; run_id: string } | null;
  result: Result | null;
  history: Card[];
  revisions?: any[];
  hypotheses_matrix?: any;
  oaai?: any;
  quick_recoveries?: any;
  density_differential?: any;
  attacking_channels?: any;
  spatial_drilldown?: {
    zone_to_sequences?: Record<string, string[]>;
    sequence_to_zones?: Record<string, string[]>;
  };
  highlights?: any[];
  model_configured: boolean;
  ended: boolean;
  format_seconds?: number;
  match_id?: string;
  session_analyses_remaining: number;
  moments_scan_truncated?: boolean;
};

export type InspectorPayload = {
  type: "sequence" | "receipt" | "claim" | "zone" | "attribution" | "sufficiency";
  title?: string;
  sequence?: PossessionSequence | null;
  receipt?: Receipt | null;
  receiptId?: string;
  claim?: Card | null;
  zoneId?: string | null;
  zoneName?: string | null;
  attribution?: any;
  sufficiencyNotice?: string;
};
