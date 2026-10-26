import { Link, useSearchParams } from "react-router-dom";

import { eur, int, shortKey } from "../../shared/lib/format";
import { useDebounced } from "../../shared/lib/useDebounced";
import { Amount, Button, EmptyState, PageHeader, QueryView, SkeletonBlock, Table, ui } from "../../shared/ui";
import { Segmented } from "../../shared/ui/Segmented";
import { FEEDER_LABEL } from "../../shared/theme/tokens";
import { PAGE, useClients } from "./api";
import styles from "./Clients.module.css";

const FEEDERS = [
  { value: "", label: "Any feeder" },
  ...Object.keys(FEEDER_LABEL).map((f) => ({ value: f, label: f })),
];

export function ClientsPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const feeder = params.get("feeder") ?? "";
  const page = Math.max(Number(params.get("page") ?? 0) || 0, 0);
  const debounced = useDebounced(q.trim().toLowerCase());
  const clients = useClients(debounced, feeder, page);

  const set = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Clients"
        lead="Clients by their pseudonymous key. Names and contact details never leave the vault; operations can see who a client is, with a reason, and every look is logged."
      />
      <div className={styles.filters}>
        <label className={styles.search}>
          <span>Find a client key</span>
          <input
            className={ui.input}
            type="search"
            value={q}
            placeholder="ck_…"
            spellCheck={false}
            autoComplete="off"
            onChange={(e) => set({ q: e.target.value })}
          />
        </label>
        <Segmented label="Feeder" options={FEEDERS} value={feeder} onChange={(v) => set({ feeder: v })} />
      </div>
      <QueryView
        query={clients}
        skeleton={<SkeletonBlock label="Loading the clients" rows={8} />}
        isEmpty={(d) => d.rows.length === 0}
        empty={
          <EmptyState
            title="No client matches"
            action={
              (q || feeder) && (
                <Button onClick={() => setParams({}, { replace: true })}>Clear the search</Button>
              )
            }
          >
            {q ? `No client key contains “${q}”.` : "No client has a commitment to this feeder."}
          </EmptyState>
        }
      >
        {(d) => {
          const pages = Math.ceil(d.total / PAGE);
          return (
            <>
              <Table caption="Clients">
                <thead>
                  <tr>
                    <th scope="col">Client</th>
                    <th scope="col">Segment</th>
                    <th scope="col">Advisor</th>
                    <th scope="col" className={ui.num}>
                      Committed
                    </th>
                    <th scope="col" className={ui.num}>
                      NAV
                    </th>
                    <th scope="col" className={ui.num}>
                      Breaks
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {d.rows.map((c) => (
                    <tr key={c.client_key}>
                      <td>
                        <Link to={`/clients/${c.client_key}`} className={styles.key}>
                          {shortKey(c.client_key)}
                        </Link>
                        <div className={styles.sub}>
                          {c.country}, {c.age_band ?? "age not given"}, {c.risk_profile}
                        </div>
                      </td>
                      <td>{c.segment}</td>
                      <td>{c.advisor}</td>
                      <td className={ui.num}>{eur(c.total_commitment)}</td>
                      <td className={ui.num}>{c.nav_eur != null ? <Amount value={c.nav_eur} /> : "n/a"}</td>
                      <td className={ui.num}>
                        {c.breaks ? int(c.breaks) : <span className={styles.sub}>none</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <nav className={styles.pager} aria-label="Pages of clients">
                <span>
                  {int(page * PAGE + 1)} to {int(Math.min((page + 1) * PAGE, d.total))} of {int(d.total)}
                </span>
                <span className={styles.pagerButtons}>
                  <Button
                    disabled={page === 0}
                    onClick={() => set({ page: page > 1 ? String(page - 1) : "" })}
                  >
                    Previous
                  </Button>
                  <Button disabled={page + 1 >= pages} onClick={() => set({ page: String(page + 1) })}>
                    Next
                  </Button>
                </span>
              </nav>
            </>
          );
        }}
      </QueryView>
    </>
  );
}
