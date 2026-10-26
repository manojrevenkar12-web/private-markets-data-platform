import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { FundDetail, FundNav } from "../../shared/api/types";
import { date, int, multiple, num, pct } from "../../shared/lib/format";
import {
  Amount,
  EmptyState,
  Figure,
  PageHeader,
  QueryView,
  Section,
  Skeleton,
  SkeletonBlock,
  Table,
  Tag,
  ui,
} from "../../shared/ui";
import { Segmented } from "../../shared/ui/Segmented";
import { FEEDER_LABEL } from "../../shared/theme/tokens";
import { HoldCard } from "../health/ReleaseHold";
import { useFund } from "./api";
import styles from "./Funds.module.css";
import { type Bar, NavChart, toEur } from "./NavChart";

type Mode = "today" | "known";

const dayBefore = (iso: string) => {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
};

/** The day before the newest version arrived: the moment what we knew last differed from now. */
function defaultKnownAt(f: FundDetail) {
  const later = f.versions.filter((v) => v.version > 1).map((v) => v.known_from);
  const pick =
    later.sort().at(-1) ??
    f.versions
      .map((v) => v.known_from)
      .sort()
      .at(-1);
  return pick ? dayBefore(pick.slice(0, 10)) : f.quarters.at(-1)!.quarter_end;
}

function barsToday(f: FundDetail): Bar[] {
  return f.quarters.map((q) => {
    const r = f.restatements.find((x) => x.period_end === q.quarter_end);
    return {
      quarter_end: q.quarter_end,
      value: num(q.nav_eur),
      source: q.nav_source,
      ghost: r ? toEur(r.previous_version_nav, q.nav_ccy, q.nav_eur) : null,
    };
  });
}

function barsKnown(f: FundDetail): Bar[] {
  const known = new Map((f.as_known ?? []).map((v) => [v.period_end, v]));
  return f.quarters.map((q) => {
    const v = known.get(q.quarter_end);
    return v
      ? {
          quarter_end: q.quarter_end,
          value: toEur(v.nav, q.nav_ccy, q.nav_eur),
          source: "statement" as const,
        }
      : { quarter_end: q.quarter_end, value: null, source: "unknown" as const };
  });
}

function Headline({ q }: { q: FundNav }) {
  const est = q.nav_source === "estimated" ? "estimated" : "reported";
  return (
    <div className={styles.figures}>
      <Figure
        value={<Amount value={q.nav_ccy} currency={q.currency} source={est} />}
        label={`NAV at ${date(q.quarter_end)}`}
      />
      <Figure
        compact
        value={<Amount value={q.commitment_ccy} currency={q.currency} />}
        label="Committed by the feeder"
      />
      <Figure
        compact
        value={<Amount value={q.paid_in_ccy} currency={q.currency} source={est} />}
        label="Paid in to date"
      />
      <Figure
        compact
        value={<Amount value={q.distributed_ccy} currency={q.currency} source={est} />}
        label="Distributed to date"
      />
      <Figure compact value={multiple(q.tvpi)} label="TVPI" />
    </div>
  );
}

function History({
  f,
  mode,
  knownAt,
  setMode,
  setKnownAt,
  refreshing,
}: {
  f: FundDetail;
  mode: Mode;
  knownAt: string;
  setMode: (m: Mode) => void;
  setKnownAt: (d: string) => void;
  refreshing: boolean;
}) {
  const showing = mode === "known" && f.as_known;
  const bars = showing ? barsKnown(f) : barsToday(f);
  const label = showing
    ? `NAV by quarter as known on ${date(knownAt)}: ${f.as_known!.length} of ${f.quarters.length} quarters had a statement.`
    : `NAV by quarter today, ${f.quarters.filter((q) => q.nav_source === "estimated").length} estimated, ${f.restatements.length} restated.`;
  return (
    <Section
      title="Net asset value by quarter"
      lead={
        showing
          ? `What the platform knew on ${date(knownAt)}: the statement versions received by that day. Statements are bitemporal, so nothing is overwritten.`
          : "Today's figures. A restated quarter keeps its first version, outlined."
      }
      actions={
        <div className={styles.timeControls}>
          <Segmented
            label="Which figures"
            options={[
              { value: "today", label: "Today" },
              { value: "known", label: "As known on" },
            ]}
            value={mode}
            onChange={setMode}
          />
          {mode === "known" && (
            <label className={styles.dateField}>
              <span className="visually-hidden">Known on</span>
              <input
                type="date"
                className={ui.input}
                value={knownAt}
                onChange={(e) => e.target.value && setKnownAt(e.target.value)}
              />
            </label>
          )}
        </div>
      }
    >
      <div aria-busy={refreshing || undefined}>
        <NavChart bars={bars} label={label} />
      </div>
    </Section>
  );
}

function Versions({ f }: { f: FundDetail }) {
  if (f.versions.length === 0)
    return (
      <EmptyState title="No statement read yet">
        Every quarter of this fund is estimated from bank flows.
      </EmptyState>
    );
  return (
    <Table caption="Statement versions received">
      <thead>
        <tr>
          <th scope="col">Quarter</th>
          <th scope="col" className={ui.num}>
            Version
          </th>
          <th scope="col" className={ui.num}>
            NAV
          </th>
          <th scope="col">Known from</th>
          <th scope="col">Replaced on</th>
          <th scope="col">Read from</th>
        </tr>
      </thead>
      <tbody>
        {f.versions.map((v) => (
          <tr key={v.file_id}>
            <td>{date(v.period_end)}</td>
            <td className={ui.num}>
              {v.version} of {v.versions}
            </td>
            <td className={ui.num}>
              <Amount value={v.nav} currency={v.currency} digits={2} />
            </td>
            <td>{date(v.known_from)}</td>
            <td>{v.known_until ? date(v.known_until) : <span className={styles.sub}>current</span>}</td>
            <td>
              <span className={styles.file}>{v.file_path.split("/").at(-1)}</span>
              <div className={styles.sub}>
                {v.parser}
                {v.unit_scale !== 1 &&
                  `, amounts in ${v.unit_scale === 1000 ? "thousands" : `units of ${int(v.unit_scale)}`}`}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Restatements({ f }: { f: FundDetail }) {
  if (f.restatements.length === 0) return null;
  return (
    <Section
      title="Restatements"
      lead="A manager sent a new version of a quarter. Clients' figures moved with it, and the old version stays on record."
    >
      <Table caption="Restated quarters">
        <thead>
          <tr>
            <th scope="col">Quarter</th>
            <th scope="col">Received</th>
            <th scope="col" className={ui.num}>
              First version
            </th>
            <th scope="col" className={ui.num}>
              Now
            </th>
            <th scope="col" className={ui.num}>
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {f.restatements.map((r) => (
            <tr key={`${r.period_end}-${r.version}`}>
              <td>{date(r.period_end)}</td>
              <td>{date(r.received_on)}</td>
              <td className={ui.num}>
                <Amount value={r.previous_version_nav} currency={r.currency} digits={2} />
              </td>
              <td className={ui.num}>
                <Amount value={r.nav} currency={r.currency} digits={2} />
              </td>
              <td className={ui.num}>
                <Tag tone={num(r.change_share) < 0 ? "bad" : "info"}>{pct(r.change_share)}</Tag>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Section>
  );
}

function FundSkeleton() {
  return (
    <div className={styles.skeletonPage} role="status" aria-label="Loading the fund">
      <Skeleton height="var(--text-3xl)" width="50%" />
      <Skeleton height="var(--space-8)" />
      <Skeleton height="14rem" />
      <SkeletonBlock label="Loading the statement versions" rows={4} />
    </div>
  );
}

export function FundPage() {
  const { fund = "" } = useParams();
  const [mode, setMode] = useState<Mode>("today");
  const [knownAt, setKnownAt] = useState<string | null>(null);
  const base = useFund(fund);
  const effective = mode === "known" && base.data ? (knownAt ?? defaultKnownAt(base.data)) : undefined;
  const asKnown = useFund(fund, effective);
  const query = mode === "known" ? asKnown : base;

  return (
    <QueryView query={query} skeleton={<FundSkeleton />}>
      {(f) => {
        const latest = f.quarters.at(-1)!;
        return (
          <>
            <p className={styles.crumb}>
              <Link to="/funds">Target funds</Link> /{" "}
              <Link to={`/funds?feeder=${latest.feeder}`}>
                {FEEDER_LABEL[latest.feeder] ?? latest.feeder}
              </Link>
            </p>
            <PageHeader
              title={latest.fund_name}
              lead={`${latest.gp}. ${latest.strategy}, ${latest.region}. Reports in ${latest.currency}.`}
            />
            <div className={styles.page}>
              <Headline q={latest} />
              {latest.nav_source === "estimated" && (
                <p className={styles.estimateNote}>
                  {date(latest.quarter_end)} is estimated ({latest.estimate_reason ?? "no statement"}): the
                  last statement
                  {latest.estimated_from ? ` (${date(latest.estimated_from)})` : ""} carried forward with the
                  capital calls and distributions the bank has booked since.
                </p>
              )}
              {f.holds.length > 0 && (
                <Section title="Held statements">
                  {f.holds.map((h) => (
                    <HoldCard key={h.file_id} hold={h} />
                  ))}
                </Section>
              )}
              <History
                f={f}
                mode={mode}
                knownAt={effective ?? ""}
                setMode={setMode}
                setKnownAt={setKnownAt}
                refreshing={query.isFetching}
              />
              <Restatements f={f} />
              <Section
                title="Statement versions"
                lead="Every statement read for this fund, with the day it became known and the day a newer version replaced it."
              >
                <Versions f={f} />
              </Section>
            </div>
          </>
        );
      }}
    </QueryView>
  );
}
