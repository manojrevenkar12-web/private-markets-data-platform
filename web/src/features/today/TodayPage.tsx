import { Link } from "react-router-dom";

import type { Overview } from "../../shared/api/types";
import { date, eur, eurM, int, time } from "../../shared/lib/format";
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
import { BREAK_KIND, FRESHNESS, OWNER, RUN_STATUS, SOURCE } from "../../shared/theme/tokens";
import { useOverview, useRuns } from "./api";
import { CallMeter } from "./CallMeter";
import { RibbonLegend, RunRibbon } from "./RunRibbon";
import styles from "./Today.module.css";

const eurMValue = (x: string) => Number(x) / 1_000_000;

function Ribbon({ published }: { published: string | null }) {
  const runs = useRuns(20);
  return (
    <QueryView
      query={runs}
      skeleton={<SkeletonBlock label="Loading the last runs" rows={1} height="var(--ribbon-height)" />}
      isEmpty={(r) => r.length === 0}
      empty={
        <EmptyState title="No runs yet">
          Run <code>pmd run</code> to load the sources, build the warehouse and publish the first numbers.
        </EmptyState>
      }
    >
      {(r) => <RunRibbon runs={r} published={published} />}
    </QueryView>
  );
}

function Lead({ o }: { o: Overview }) {
  const latest = o.latest_run;
  const stuck = latest.run_id !== o.published_run.run_id;
  return (
    <>
      Published {time(o.published_run.finished_at)} from run{" "}
      <Link to={`/runs/${o.published_run.run_id}`}>{o.published_run.run_id}</Link>.{" "}
      {stuck && (
        <>
          The newest run, <Link to={`/runs/${latest.run_id}`}>{latest.run_id}</Link>, is{" "}
          {(RUN_STATUS[latest.status]?.label ?? latest.status).toLowerCase()}; clients keep seeing the
          published one.
        </>
      )}
    </>
  );
}

function Feeders({ o }: { o: Overview }) {
  return (
    <div className={styles.feeders}>
      {o.feeders.map((f) => (
        <article key={f.feeder} className={styles.feeder} aria-labelledby={`feeder-${f.feeder}`}>
          <h3 id={`feeder-${f.feeder}`}>{f.feeder_name}</h3>
          <Figure
            value={
              <Amount
                value={eurMValue(f.nav_eur)}
                currency="m EUR"
                digits={1}
                source={f.has_estimates ? "estimated" : "reported"}
                title={eur(f.nav_eur)}
              />
            }
            label={`NAV at ${date(f.quarter_end)}`}
          />
          <dl className={styles.facts}>
            <div>
              <dt>Commitments</dt>
              <dd>{eurM(f.total_commitment)}</dd>
            </div>
            <div>
              <dt>Cash at the custodian</dt>
              <dd>{eurM(f.cash_eur)}</dd>
            </div>
          </dl>
          {f.has_estimates && (
            <p className={styles.footnote}>
              Some target funds are carried forward from their last statement.{" "}
              <Link to={`/funds?feeder=${f.feeder}`}>See which</Link>
            </p>
          )}
        </article>
      ))}
    </div>
  );
}

function Cash({ o }: { o: Overview }) {
  if (o.cash_now.length === 0)
    return (
      <EmptyState title="No capital call is open">
        The next calls go out at the start of the quarter; this panel shows them as money arrives.
      </EmptyState>
    );
  return (
    <ul className={styles.calls}>
      {o.cash_now.map((c) => (
        <li key={c.call_id} className={styles.call}>
          <div className={styles.callHead}>
            <strong>{c.call_id}</strong>
            <span>due {date(c.due_date)}</span>
          </div>
          <CallMeter call={c} />
          <dl className={styles.callFacts}>
            <div>
              <dt>Booked by the custodian</dt>
              <dd>
                <Amount value={c.booked_eur} />
              </dd>
            </div>
            <div>
              <dt>Arrived since the {date(c.last_statement_on)} statement</dt>
              <dd>
                <Amount value={c.arrived_since_statement_eur} source="provisional" />
              </dd>
            </div>
            <div>
              <dt>Outstanding</dt>
              <dd>
                <Amount value={c.outstanding_eur} />, {int(c.clients_not_paid)} of {int(c.clients)} clients
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function Breaks({ o }: { o: Overview }) {
  if (o.breaks.length === 0)
    return (
      <EmptyState title="Nothing to reconcile">Every payment, receipt and statement matches.</EmptyState>
    );
  const total = o.breaks.reduce((s, b) => s + b.open, 0);
  return (
    <Table caption="Open breaks by kind">
      <thead>
        <tr>
          <th scope="col">Kind</th>
          <th scope="col">Owner</th>
          <th scope="col" className={ui.num}>
            Open
          </th>
          <th scope="col" className={ui.num}>
            Amount
          </th>
        </tr>
      </thead>
      <tbody>
        {o.breaks.map((b) => (
          <tr key={b.kind}>
            <td>
              <Link to={`/breaks?kind=${b.kind}`} className={styles.kindLink}>
                <Tag tone={BREAK_KIND[b.kind]?.tone ?? "quiet"}>{BREAK_KIND[b.kind]?.label ?? b.kind}</Tag>
              </Link>
            </td>
            <td>{OWNER[b.owner] ?? b.owner}</td>
            <td className={ui.num}>{int(b.open)}</td>
            <td className={ui.num}>{Number(b.amount_eur) ? eur(b.amount_eur) : "no amount"}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" colSpan={2}>
            All open breaks
          </th>
          <td className={ui.num}>{int(total)}</td>
          <td />
        </tr>
      </tfoot>
    </Table>
  );
}

function Sources({ o }: { o: Overview }) {
  const bySource = new Map<string, { status: string; feeds: number }[]>();
  for (const f of o.freshness) bySource.set(f.source, [...(bySource.get(f.source) ?? []), f]);
  return (
    <ul className={styles.sources}>
      {[...bySource.entries()].map(([source, rows]) => (
        <li key={source}>
          <span className={styles.sourceName}>{SOURCE[source] ?? source}</span>
          <span className={styles.sourceTags}>
            {rows.map((r) => (
              <Tag key={r.status} tone={FRESHNESS[r.status]?.tone ?? "quiet"}>
                {int(r.feeds)} {(FRESHNESS[r.status]?.label ?? r.status).toLowerCase()}
              </Tag>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

function TodaySkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label="Loading today's numbers">
      <Skeleton height="var(--text-3xl)" width="60%" />
      <Skeleton height="var(--ribbon-height)" />
      <div className={styles.feeders}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height="12rem" />
        ))}
      </div>
    </div>
  );
}

export function TodayPage() {
  const overview = useOverview();
  return (
    <QueryView query={overview} skeleton={<TodaySkeleton />}>
      {(o) => (
        <>
          <PageHeader title={`What clients see on ${date(o.as_of)}`} lead={<Lead o={o} />} />
          <div className={styles.grid}>
            <Section
              title="Every run, gate by gate"
              lead="Each run builds the warehouse into a schema of its own. Clients only see it when no gate stops it."
              actions={<Link to="/runs">All runs</Link>}
            >
              <Ribbon published={o.published_run.run_id} />
              <RibbonLegend />
            </Section>
            <Section
              title="Feeder funds"
              lead={`${int(o.clients.clients)} clients have committed ${eurM(o.clients.commitments)}.`}
            >
              <Feeders o={o} />
            </Section>
            <div className={styles.split}>
              <Section
                title="Capital calls open now"
                lead="Booked figures come from custodian statements; the rest from the instant payment feed."
              >
                <Cash o={o} />
              </Section>
              <Section title="Open breaks" actions={<Link to="/breaks">Work the queue</Link>}>
                <Breaks o={o} />
              </Section>
            </div>
            <Section title="Sources" actions={<Link to="/health">Data health</Link>}>
              <Sources o={o} />
            </Section>
          </div>
        </>
      )}
    </QueryView>
  );
}
