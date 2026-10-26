/** The shapes the platform API returns (src/pmd/api.py). Money arrives as decimal strings. */

export type Money = string;

export interface Problem {
  title: string;
  status: number;
  detail?: string;
}

export interface Gate {
  name: string;
  severity: "block" | "warn";
  passed: boolean;
  detail: string;
  count: number;
}

export interface Run {
  run_id: string;
  status: "published" | "audited" | "blocked" | "built" | "build_failed";
  build_schema: string;
  as_of: string;
  started_at: string;
  finished_at: string | null;
  gates: Gate[];
  counts: Record<string, number>;
  diff?: Record<string, MartDiff> | null;
  build?: {
    ok: boolean;
    models: number;
    tests: number;
    failures: { node: string; message: string }[];
  } | null;
  approved_by?: string | null;
  approval_note?: string | null;
}

export interface MartDiff {
  rows_old?: number;
  rows_new?: number;
  added?: number;
  removed?: number;
  changed?: number;
  columns_added?: string[];
  columns_removed?: string[];
  totals_changed?: Record<string, { old: number; new: number }>;
  status?: string;
}

export interface FeederNav {
  feeder: string;
  feeder_name: string;
  quarter_end: string;
  nav_eur: Money;
  cash_eur: Money;
  total_commitment: Money;
  has_estimates: boolean;
}

export interface CashCall {
  call_id: string;
  feeder: string;
  notice_date: string;
  due_date: string;
  clients: number;
  expected_eur: Money;
  booked_eur: Money;
  arrived_since_statement_eur: Money;
  outstanding_eur: Money;
  clients_not_paid: number;
  last_event_at: string | null;
  last_statement_on: string | null;
}

export interface Overview {
  as_of: string;
  published_run: Pick<Run, "run_id" | "status" | "as_of" | "finished_at" | "gates">;
  latest_run: Pick<Run, "run_id" | "status" | "started_at" | "finished_at" | "gates">;
  feeders: FeederNav[];
  clients: { clients: number; commitments: Money };
  breaks: { kind: string; owner: string; open: number; amount_eur: Money }[];
  freshness: { source: string; status: string; feeds: number }[];
  cash_now: CashCall[];
}

export interface Feed {
  source: string;
  feed: string;
  label: string;
  latest: string | null;
  last_received_on: string | null;
  due: string | null;
  status: "fresh" | "late" | "missing";
}

export interface Hold {
  file_id: number;
  fund: string;
  fund_name: string;
  period_end: string;
  version: number;
  received_on: string;
  hold_reason: string;
  nav: Money;
  prev_nav: Money | null;
  unexplained_move: Money | null;
  currency: string;
  file_path: string;
}

export interface Freshness {
  feeds: Feed[];
  quarantine: {
    file_id: number;
    source: string;
    path: string;
    received_on: string;
    rule: string;
    detail: string;
    at: string;
  }[];
  duplicates: { path: string; same_as: string; file_id: number; seen_at: string }[];
  dead_events: { event_id: string | null; rule: string; detail: string; at: string }[];
  holds: Hold[];
  erasures: {
    request_id: string;
    client_key: string;
    requested_on: string;
    status: string;
    reason: string;
  }[];
}

export interface Break {
  break_id: string;
  kind: string;
  owner: "operations" | "fund_accounting";
  feeder: string | null;
  fund: string | null;
  client_key: string | null;
  reference: string | null;
  expected_eur: Money | null;
  actual_eur: Money | null;
  difference_eur: Money | null;
  opened_on: string | null;
  age_days: number;
  detail: string;
  last_action: string;
  last_note: string | null;
  last_actor: string | null;
  last_action_at: string | null;
  status: "open" | "resolved";
}

export interface FundNav {
  fund: string;
  fund_name: string;
  gp: string;
  strategy: string;
  region: string;
  feeder: string;
  quarter_end: string;
  currency: string;
  commitment_ccy: Money;
  paid_in_ccy: Money;
  distributed_ccy: Money;
  nav_ccy: Money;
  usd_per_eur: Money;
  nav_eur: Money;
  nav_source: "statement" | "estimated";
  estimate_reason: string | null;
  estimated_from: string | null;
  statement_file_id: number | null;
  statement_version: number | null;
  tvpi: Money | null;
  restatements?: number;
}

export interface StatementVersion {
  file_id: number;
  period_end: string;
  version: number;
  versions: number;
  nav: Money;
  paid_in: Money;
  distributed: Money;
  currency: string;
  known_from: string;
  known_until: string | null;
  parser: string;
  unit_scale: number;
  file_path: string;
}

export interface Restatement {
  fund: string;
  period_end: string;
  version: number;
  file_id: number;
  received_on: string;
  previous_version_nav: Money;
  nav: Money;
  change_ccy: Money;
  change_share: Money;
  currency: string;
}

export interface FundDetail {
  fund: string;
  quarters: FundNav[];
  versions: StatementVersion[];
  holds: Hold[];
  restatements: Restatement[];
  known_at?: string;
  as_known?: StatementVersion[];
}

export interface ClientRow {
  client_key: string;
  segment: string;
  risk_profile: string;
  country: string;
  age_band: string | null;
  onboarded_on: string | null;
  advisor: string;
  status: string;
  total_commitment: Money;
  feeders: number;
  nav_eur?: Money | null;
  breaks?: number;
}

export interface Performance {
  client_key: string;
  feeder: string;
  as_of_quarter: string;
  commitment: Money;
  paid_in_eur: Money;
  distributed_eur: Money;
  nav_eur: Money;
  unfunded_eur: Money;
  dpi: Money | null;
  tvpi: Money | null;
  irr: Money | null;
  nav_has_estimates: boolean;
}

export interface LookThrough {
  client_key: string;
  feeder: string;
  quarter_end: string;
  fund: string | null;
  fund_name: string;
  strategy: string;
  region: string | null;
  currency: string;
  nav_eur: Money;
  nav_source: string;
  estimate_reason: string | null;
}

export interface ClientDetail {
  client: ClientRow;
  performance: Performance[];
  lookthrough: LookThrough[];
  positions: {
    feeder: string;
    quarter_end: string;
    nav_eur: Money;
    paid_in_eur: Money;
    distributed_eur: Money;
    nav_has_estimates: boolean;
  }[];
  payments: {
    call_id: string;
    feeder: string;
    due_date: string;
    expected_eur: Money;
    received_eur: Money;
    provisional_eur: Money;
    status: string;
  }[];
  breaks: Break[];
}

export interface Identity {
  client_key: string;
  client_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  city: string;
  logged: boolean;
}

export interface Lineage {
  nodes: { id: string; name: string; layer: string; description: string }[];
  edges: { from: string; to: string }[];
}
