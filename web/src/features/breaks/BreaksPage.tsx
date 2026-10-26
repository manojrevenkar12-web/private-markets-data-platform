import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import type { Break } from "../../shared/api/types";
import { eur, humanise, int, shortKey } from "../../shared/lib/format";
import { Button, EmptyState, PageHeader, QueryView, SkeletonBlock, Table, Tag, ui } from "../../shared/ui";
import { Segmented } from "../../shared/ui/Segmented";
import { BREAK_KIND, OWNER } from "../../shared/theme/tokens";
import { ActOnBreak } from "./ActOnBreak";
import { type BreakFilter, useBreaks } from "./api";
import styles from "./Breaks.module.css";

const STEP = 50;

const OWNERS = [
  { value: "", label: "Everyone" },
  { value: "operations", label: OWNER.operations! },
  { value: "fund_accounting", label: OWNER.fund_accounting! },
];

const STATUSES = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "All" },
] as const;

function Rows({ rows, onAct }: { rows: Break[]; onAct: (b: Break) => void }) {
  const [shown, setShown] = useState(STEP);
  return (
    <>
      <Table caption="Breaks">
        <thead>
          <tr>
            <th scope="col">Kind</th>
            <th scope="col">Reference</th>
            <th scope="col">Client</th>
            <th scope="col" className={ui.num}>
              Difference
            </th>
            <th scope="col" className={ui.num}>
              Open for
            </th>
            <th scope="col">Last action</th>
            <th scope="col">
              <span className="visually-hidden">Act</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, shown).map((b) => (
            <tr key={b.break_id}>
              <td>
                <Tag tone={BREAK_KIND[b.kind]?.tone ?? "quiet"}>
                  {BREAK_KIND[b.kind]?.label ?? humanise(b.kind)}
                </Tag>
                <div className={styles.detail}>{b.detail}</div>
              </td>
              <td>{b.reference ?? (b.fund ? <Link to={`/funds/${b.fund}`}>{b.fund}</Link> : "none")}</td>
              <td>
                {b.client_key ? (
                  <Link to={`/clients/${b.client_key}`}>{shortKey(b.client_key)}</Link>
                ) : (
                  "none"
                )}
              </td>
              <td className={ui.num}>{b.difference_eur != null ? eur(b.difference_eur, 2) : "n/a"}</td>
              <td className={ui.num}>{b.opened_on ? `${int(b.age_days)} days` : "n/a"}</td>
              <td>
                {b.last_action_at ? (
                  <>
                    {humanise(b.last_action)} by {b.last_actor}
                    {b.last_note && <div className={styles.detail}>{b.last_note}</div>}
                  </>
                ) : (
                  <span className={styles.none}>No one yet</span>
                )}
              </td>
              <td>
                <Button
                  onClick={() => onAct(b)}
                  aria-label={`Act on ${BREAK_KIND[b.kind]?.label ?? b.kind} ${b.reference ?? b.fund ?? ""}`}
                >
                  Act
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <div className={styles.more}>
        <span>
          Showing {int(Math.min(shown, rows.length))} of {int(rows.length)}
        </span>
        {shown < rows.length && (
          <Button onClick={() => setShown(shown + STEP)}>
            Show {int(Math.min(STEP, rows.length - shown))} more
          </Button>
        )}
      </div>
    </>
  );
}

export function BreaksPage() {
  const [params, setParams] = useSearchParams();
  const filter: BreakFilter = {
    owner: params.get("owner") ?? undefined,
    kind: params.get("kind") ?? undefined,
    status: (params.get("status") as BreakFilter["status"] | null) ?? "open",
  };
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value && !(key === "status" && value === "open")) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };
  const breaks = useBreaks(filter);
  const [acting, setActing] = useState<Break | null>(null);
  const kindLabel = filter.kind ? (BREAK_KIND[filter.kind]?.label ?? humanise(filter.kind)) : null;

  return (
    <>
      <PageHeader
        title="Breaks"
        lead="Every payment, receipt and statement that does not match, with who owns it. A break keeps its id across runs, so what someone did about it stays with it."
      />
      <div className={styles.filters}>
        <Segmented
          label="Owner"
          options={OWNERS}
          value={filter.owner ?? ""}
          onChange={(v) => set("owner", v)}
        />
        <Segmented
          label="Status"
          options={[...STATUSES]}
          value={filter.status}
          onChange={(v) => set("status", v)}
        />
        <label className={styles.kind}>
          <span>Kind</span>
          <select
            className={ui.input}
            value={filter.kind ?? ""}
            onChange={(e) => set("kind", e.target.value)}
          >
            <option value="">Every kind</option>
            {Object.entries(BREAK_KIND).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <QueryView
        query={breaks}
        skeleton={<SkeletonBlock label="Loading the breaks" rows={8} height="var(--space-7)" />}
        isEmpty={(r) => r.length === 0}
        empty={
          <EmptyState
            title={filter.status === "open" ? "Nothing open here" : "No breaks match"}
            action={
              (filter.kind || filter.owner || filter.status !== "open") && (
                <Button onClick={() => setParams(new URLSearchParams(), { replace: true })}>
                  Show every open break
                </Button>
              )
            }
          >
            {kindLabel ? `No ${kindLabel.toLowerCase()} break` : "No break"} matches these filters.
          </EmptyState>
        }
      >
        {(rows) => <Rows key={JSON.stringify(filter)} rows={rows} onAct={setActing} />}
      </QueryView>
      <ActOnBreak item={acting} onClose={() => setActing(null)} />
    </>
  );
}
