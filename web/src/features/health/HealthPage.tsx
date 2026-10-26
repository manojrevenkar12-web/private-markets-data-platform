import { Link } from "react-router-dom";

import type { Feed, Freshness } from "../../shared/api/types";
import { date, humanise, shortKey, time } from "../../shared/lib/format";
import { EmptyState, PageHeader, QueryView, Section, SkeletonBlock, Table, Tag } from "../../shared/ui";
import { FRESHNESS, SOURCE } from "../../shared/theme/tokens";
import { useFreshness } from "./api";
import styles from "./Health.module.css";
import { HoldCard } from "./ReleaseHold";

const ERASURE: Record<string, { label: string; tone: "good" | "watch" | "quiet" }> = {
  erased: { label: "Erased", tone: "good" },
  retention_hold: { label: "Kept for retention", tone: "watch" },
};

function Feeds({ feeds }: { feeds: Feed[] }) {
  const sources = [...new Set(feeds.map((f) => f.source))];
  return (
    <div className={styles.feedGroups}>
      {sources.map((s) => (
        <Table key={s} caption={SOURCE[s] ?? s}>
          <thead>
            <tr>
              <th scope="col">{SOURCE[s] ?? s}</th>
              <th scope="col">Latest figures</th>
              <th scope="col">Received</th>
              <th scope="col">Next due</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {feeds
              .filter((f) => f.source === s)
              .map((f) => (
                <tr key={f.feed}>
                  <td>{f.label}</td>
                  <td>{date(f.latest)}</td>
                  <td>{date(f.last_received_on)}</td>
                  <td>{date(f.due)}</td>
                  <td>
                    <Tag tone={FRESHNESS[f.status]?.tone ?? "quiet"}>
                      {FRESHNESS[f.status]?.label ?? f.status}
                    </Tag>
                  </td>
                </tr>
              ))}
          </tbody>
        </Table>
      ))}
    </div>
  );
}

function Rejected({ h }: { h: Freshness }) {
  const none = h.quarantine.length + h.duplicates.length + h.dead_events.length === 0;
  if (none)
    return (
      <EmptyState title="Nothing rejected">Every file and event that arrived met its contract.</EmptyState>
    );
  return (
    <ul className={styles.list}>
      {h.quarantine.map((q) => (
        <li key={`q-${q.file_id}`}>
          <Tag tone="bad">Quarantined</Tag>
          <span className={styles.path}>{q.path}</span>
          <p>
            {humanise(q.rule)}: {q.detail}. Received {date(q.received_on)}.
          </p>
        </li>
      ))}
      {h.duplicates.map((d) => (
        <li key={`d-${d.file_id}-${d.path}`}>
          <Tag tone="quiet">Duplicate, ignored</Tag>
          <span className={styles.path}>{d.path}</span>
          <p>
            Same bytes as {d.same_as}. Seen {time(d.seen_at)}.
          </p>
        </li>
      ))}
      {h.dead_events.map((e, i) => (
        <li key={`e-${e.event_id ?? i}`}>
          <Tag tone="bad">Dead letter</Tag>
          <span className={styles.path}>{e.event_id ?? "event without id"}</span>
          <p>
            {humanise(e.rule)}: {e.detail}. {time(e.at)}.
          </p>
        </li>
      ))}
    </ul>
  );
}

function Erasures({ h }: { h: Freshness }) {
  if (h.erasures.length === 0)
    return (
      <EmptyState title="No erasure requests">
        Requests to delete personal data appear here with what was decided.
      </EmptyState>
    );
  return (
    <Table caption="Erasure requests">
      <thead>
        <tr>
          <th scope="col">Request</th>
          <th scope="col">Client</th>
          <th scope="col">Asked on</th>
          <th scope="col">Decision</th>
        </tr>
      </thead>
      <tbody>
        {h.erasures.map((e) => (
          <tr key={e.request_id}>
            <td>{e.request_id}</td>
            <td>
              {e.status === "erased" ? (
                shortKey(e.client_key)
              ) : (
                <Link to={`/clients/${e.client_key}`}>{shortKey(e.client_key)}</Link>
              )}
            </td>
            <td>{date(e.requested_on)}</td>
            <td>
              <Tag tone={ERASURE[e.status]?.tone ?? "quiet"}>
                {ERASURE[e.status]?.label ?? humanise(e.status)}
              </Tag>
              <div className={styles.sub}>{e.reason}</div>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function HealthPage() {
  const health = useFreshness();
  return (
    <>
      <PageHeader
        title="Data health"
        lead="Whether every source arrived on time, what was rejected at the door and why, and which statements their checks held back."
      />
      <QueryView query={health} skeleton={<SkeletonBlock label="Loading data health" rows={6} />}>
        {(h) => (
          <div className={styles.page}>
            <Section
              title="Feeds"
              lead="A GP statement is due 90 days after its quarter; custodian statements and the instant feed every business day."
            >
              <Feeds feeds={h.feeds} />
            </Section>
            <Section
              title="Held statements"
              lead="A statement whose checks fail is kept out of the numbers; its quarter is estimated until someone decides."
            >
              {h.holds.length === 0 ? (
                <EmptyState title="No statement is held">Every statement read passed its checks.</EmptyState>
              ) : (
                <div className={styles.holds}>
                  {h.holds.map((x) => (
                    <HoldCard key={x.file_id} hold={x} />
                  ))}
                </div>
              )}
            </Section>
            <Section
              title="Rejected at the door"
              lead="Files that broke their contract, files seen before, and payment events nobody could apply."
            >
              <Rejected h={h} />
            </Section>
            <Section
              title="Erasure requests"
              lead="Personal data lives only in the vault. A prospect's is deleted; an investor's is kept for the statutory retention period."
            >
              <Erasures h={h} />
            </Section>
          </div>
        )}
      </QueryView>
    </>
  );
}
