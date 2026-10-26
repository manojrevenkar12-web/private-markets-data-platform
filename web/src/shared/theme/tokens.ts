/** Words and tones for the states the API reports, so every screen names them the same way. */

export type Tone = "good" | "watch" | "bad" | "info" | "quiet" | "estimate";

/** Motion, mirrored from tokens.css for Framer Motion, which needs numbers. */
export const MOTION = {
  move: 0.38,
  draw: 0.6,
  quick: 0.14,
  stagger: 0.03,
  ease: [0.2, 0.8, 0.2, 1] as [number, number, number, number],
} as const;

export const BREAK_KIND: Record<string, { label: string; tone: Tone }> = {
  payment_overdue: { label: "Call overdue", tone: "bad" },
  payment_short: { label: "Paid short", tone: "watch" },
  payment_over: { label: "Paid too much", tone: "watch" },
  payment_duplicate: { label: "Paid twice", tone: "bad" },
  unmatched_receipt: { label: "Money nobody can place", tone: "bad" },
  statement_held: { label: "Statement held", tone: "estimate" },
  statement_late: { label: "Statement late", tone: "estimate" },
  gp_cash_mismatch: { label: "GP cash mismatch", tone: "bad" },
};

export const OWNER: Record<string, string> = {
  operations: "Operations",
  fund_accounting: "Fund accounting",
};

export const PAYMENT_STATUS: Record<string, { label: string; tone: Tone }> = {
  paid: { label: "Paid", tone: "good" },
  paid_late: { label: "Paid late", tone: "quiet" },
  part_paid: { label: "Part paid", tone: "watch" },
  short: { label: "Short", tone: "watch" },
  over: { label: "Over", tone: "watch" },
  duplicate: { label: "Paid twice", tone: "bad" },
  overdue: { label: "Overdue", tone: "bad" },
  open: { label: "Open", tone: "info" },
};

export const FRESHNESS: Record<string, { label: string; tone: Tone }> = {
  fresh: { label: "Up to date", tone: "good" },
  late: { label: "Late", tone: "bad" },
  missing: { label: "Nothing yet", tone: "quiet" },
};

export const SOURCE: Record<string, string> = {
  gp_statement: "GP statements",
  bank_statement: "Custodian statements",
  payment_events: "Instant payment feed",
};

export const RUN_STATUS: Record<string, { label: string; tone: Tone }> = {
  published: { label: "Published", tone: "good" },
  audited: { label: "Audited", tone: "info" },
  blocked: { label: "Blocked", tone: "bad" },
  built: { label: "Built", tone: "quiet" },
  build_failed: { label: "Build failed", tone: "bad" },
};

export const ROLES = [
  { value: "analyst", label: "Analyst" },
  { value: "operations", label: "Operations" },
  { value: "fund_accounting", label: "Fund accounting" },
] as const;

export type Role = (typeof ROLES)[number]["value"];

export const FEEDER_LABEL: Record<string, string> = {
  PE5: "Private Equity V",
  VC3: "Venture III",
  PD1: "Private Debt I",
};

/** The gates every build passes before clients see it, in the order they run (src/pmd/publish.py). */
export const GATES: { name: string; label: string; means: string }[] = [
  { name: "dbt_tests", label: "Models and tests", means: "Every dbt model built and every test passed." },
  { name: "marts_not_empty", label: "Marts have rows", means: "No client-facing mart came out empty." },
  {
    name: "nav_drift",
    label: "NAV drift",
    means: "No fund NAV clients have seen moved more than the threshold without a new statement.",
  },
  {
    name: "unmatched_receipts",
    label: "Unplaced money",
    means: "No receipt has waited too long for an owner.",
  },
  { name: "overdue_calls", label: "Overdue calls", means: "Every capital call due has been paid." },
  { name: "late_statements", label: "Late statements", means: "Every GP statement due has arrived." },
  { name: "statement_holds", label: "Held statements", means: "No statement is held back by its checks." },
];

export const SEVERITY: Record<string, string> = { block: "Stops publishing", warn: "Warns" };

export const LAYER: Record<string, { label: string; order: number }> = {
  source: { label: "Sources", order: 0 },
  staging: { label: "Staging", order: 1 },
  intermediate: { label: "Intermediate", order: 2 },
  marts: { label: "Marts", order: 3 },
};
