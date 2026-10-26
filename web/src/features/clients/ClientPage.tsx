import { Link, useParams } from "react-router-dom";

import type { ClientDetail } from "../../shared/api/types";
import { date, eur, humanise, multiple, num, pct, shortKey } from "../../shared/lib/format";
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
import { BREAK_KIND, FEEDER_LABEL, PAYMENT_STATUS } from "../../shared/theme/tokens";
import { useClient } from "./api";
import styles from "./Clients.module.css";
import { Reveal } from "./Reveal";

const PAYMENTS_SHOWN = 12;

function Performance({ c }: { c: ClientDetail }) {
  if (c.performance.length === 0)
    return <EmptyState title="No position yet">The first capital call has not been paid.</EmptyState>;
  return (
    <Table caption="Performance by feeder">
      <thead>
        <tr>
          <th scope="col">Feeder</th>
          <th scope="col" className={ui.num}>
            Committed
          </th>
          <th scope="col" className={ui.num}>
            Paid in
          </th>
          <th scope="col" className={ui.num}>
            Distributed
          </th>
          <th scope="col" className={ui.num}>
            NAV
          </th>
          <th scope="col" className={ui.num}>
            TVPI
          </th>
          <th scope="col" className={ui.num}>
            IRR
          </th>
        </tr>
      </thead>
      <tbody>
        {c.performance.map((p) => (
          <tr key={p.feeder}>
            <th scope="row">
              {FEEDER_LABEL[p.feeder] ?? p.feeder}
              <div className={styles.sub}>at {date(p.as_of_quarter)}</div>
            </th>
            <td className={ui.num}>{eur(p.commitment)}</td>
            <td className={ui.num}>{eur(p.paid_in_eur)}</td>
            <td className={ui.num}>{eur(p.distributed_eur)}</td>
            <td className={ui.num}>
              <Amount value={p.nav_eur} source={p.nav_has_estimates ? "estimated" : "reported"} />
            </td>
            <td className={ui.num}>{multiple(p.tvpi)}</td>
            <td className={ui.num}>{p.irr != null ? pct(p.irr) : "too early"}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function LookThrough({ c }: { c: ClientDetail }) {
  if (c.lookthrough.length === 0)
    return <EmptyState title="Nothing to look through yet">No target fund has called capital.</EmptyState>;
  const total = c.lookthrough.reduce((s, l) => s + num(l.nav_eur), 0);
  return (
    <Table caption="Look-through to target funds">
      <thead>
        <tr>
          <th scope="col">Target fund</th>
          <th scope="col">Strategy</th>
          <th scope="col" className={ui.num}>
            Share of NAV
          </th>
          <th scope="col" className={ui.num}>
            NAV
          </th>
        </tr>
      </thead>
      <tbody>
        {c.lookthrough.map((l) => (
          <tr key={`${l.feeder}-${l.fund ?? "cash"}`}>
            <td>
              {l.fund ? <Link to={`/funds/${l.fund}`}>{l.fund_name}</Link> : l.fund_name}
              <div className={styles.sub}>via {l.feeder}</div>
            </td>
            <td>{l.strategy}</td>
            <td className={ui.num}>{total ? pct(num(l.nav_eur) / total) : "n/a"}</td>
            <td className={ui.num}>
              <Amount
                value={l.nav_eur}
                source={l.nav_source === "estimated" ? "estimated" : "reported"}
                title={l.estimate_reason ?? undefined}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Payments({ c }: { c: ClientDetail }) {
  if (c.payments.length === 0)
    return <EmptyState title="No capital call yet">Payments appear once a feeder calls capital.</EmptyState>;
  return (
    <Table caption="Capital call payments">
      <thead>
        <tr>
          <th scope="col">Call</th>
          <th scope="col">Due</th>
          <th scope="col" className={ui.num}>
            Called
          </th>
          <th scope="col" className={ui.num}>
            Received
          </th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>
        {c.payments.slice(0, PAYMENTS_SHOWN).map((p) => (
          <tr key={p.call_id}>
            <td>{p.call_id}</td>
            <td>{date(p.due_date)}</td>
            <td className={ui.num}>{eur(p.expected_eur, 2)}</td>
            <td className={ui.num}>
              <Amount value={p.received_eur} digits={2} />
              {num(p.provisional_eur) > 0 && (
                <div>
                  <Amount value={p.provisional_eur} digits={2} source="provisional" />
                </div>
              )}
            </td>
            <td>
              <Tag tone={PAYMENT_STATUS[p.status]?.tone ?? "quiet"}>
                {PAYMENT_STATUS[p.status]?.label ?? humanise(p.status)}
              </Tag>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Breaks({ c }: { c: ClientDetail }) {
  if (c.breaks.length === 0) return <p className={styles.sub}>Nothing open or resolved for this client.</p>;
  return (
    <ul className={styles.breaks}>
      {c.breaks.map((b) => (
        <li key={b.break_id}>
          <Tag tone={BREAK_KIND[b.kind]?.tone ?? "quiet"}>
            {BREAK_KIND[b.kind]?.label ?? humanise(b.kind)}
          </Tag>{" "}
          {b.reference}: {b.detail} {b.status === "resolved" ? "Resolved." : ""}{" "}
          <Link to={`/breaks?kind=${b.kind}&status=all`}>In the queue</Link>
        </li>
      ))}
    </ul>
  );
}

function ClientSkeleton() {
  return (
    <div className={styles.page} role="status" aria-label="Loading the client">
      <Skeleton height="var(--text-3xl)" width="40%" />
      <Skeleton height="var(--space-8)" />
      <SkeletonBlock label="Loading the positions" rows={4} />
    </div>
  );
}

export function ClientPage() {
  const { key = "" } = useParams();
  const client = useClient(key);
  return (
    <QueryView query={client} skeleton={<ClientSkeleton />}>
      {(c) => {
        const nav = c.performance.reduce((s, p) => s + num(p.nav_eur), 0);
        const paid = c.performance.reduce((s, p) => s + num(p.paid_in_eur), 0);
        const unfunded = c.performance.reduce((s, p) => s + num(p.unfunded_eur), 0);
        const est = c.performance.some((p) => p.nav_has_estimates);
        return (
          <>
            <p className={styles.crumb}>
              <Link to="/clients">Clients</Link>
            </p>
            <PageHeader
              title={<span className={styles.keyTitle}>{shortKey(c.client.client_key)}</span>}
              lead={`${c.client.segment}, ${c.client.risk_profile} profile, ${c.client.country}. Advised by ${c.client.advisor} since ${date(c.client.onboarded_on)}.`}
              actions={<Reveal clientKey={c.client.client_key} />}
            />
            <div className={styles.page}>
              <div className={styles.figures}>
                <Figure
                  value={<Amount value={nav} source={est ? "estimated" : "reported"} />}
                  label="NAV across feeders"
                />
                <Figure compact value={eur(c.client.total_commitment)} label="Committed" />
                <Figure compact value={eur(paid)} label="Paid in" />
                <Figure compact value={eur(unfunded)} label="Still to be called" />
              </div>
              <Section
                title="Performance"
                lead="Net of the feeder's costs, from the client's own cash flows. IRR needs a year of history."
              >
                <Performance c={c} />
              </Section>
              <Section
                title="What the client owns underneath"
                lead="The client's share of each target fund, through the feeders, at the latest quarter."
              >
                <LookThrough c={c} />
              </Section>
              <div className={styles.split}>
                <Section
                  title="Capital calls"
                  lead={
                    c.payments.length > PAYMENTS_SHOWN
                      ? `The latest ${PAYMENTS_SHOWN} of ${c.payments.length}.`
                      : undefined
                  }
                >
                  <Payments c={c} />
                </Section>
                <Section title="Breaks">
                  <Breaks c={c} />
                </Section>
              </div>
            </div>
          </>
        );
      }}
    </QueryView>
  );
}
