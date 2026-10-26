import { Link, useParams } from "react-router-dom";

import type { MartDiff, Run } from "../../shared/api/types";
import { humanise, int, time } from "../../shared/lib/format";
import {
  EmptyState,
  Notice,
  PageHeader,
  QueryView,
  Section,
  SkeletonBlock,
  Table,
  Tag,
  ui,
} from "../../shared/ui";
import { GATES, RUN_STATUS, SEVERITY } from "../../shared/theme/tokens";
import { useRun } from "./api";
import styles from "./Runs.module.css";

function Gates({ run }: { run: Run }) {
  return (
    <ol className={styles.gates}>
      {GATES.map((meta) => {
        const g = run.gates.find((x) => x.name === meta.name);
        const tone = !g ? "quiet" : g.passed ? "good" : g.severity === "block" ? "bad" : "watch";
        const word = !g
          ? "Did not run"
          : g.passed
            ? "Passed"
            : g.severity === "block"
              ? "Stopped the publish"
              : "Warned";
        return (
          <li key={meta.name} className={styles.gate}>
            <div className={styles.gateHead}>
              <strong>{meta.label}</strong>
              <Tag tone={tone}>{word}</Tag>
            </div>
            <p className={styles.sub}>
              {meta.means} {SEVERITY[g?.severity ?? ""] ?? ""}
              {g ? ` when it fails.` : ""}
            </p>
            {g && !g.passed && <p className={styles.gateDetail}>{g.detail}</p>}
          </li>
        );
      })}
    </ol>
  );
}

function changedOnly(diff: Record<string, MartDiff>) {
  return Object.entries(diff).filter(
    ([, d]) =>
      d.status ||
      d.added ||
      d.removed ||
      d.changed ||
      (d.columns_added?.length ?? 0) + (d.columns_removed?.length ?? 0) > 0,
  );
}

function Diff({ run }: { run: Run }) {
  if (!run.diff)
    return (
      <EmptyState title="Nothing to compare">
        This was the first build, or the build failed before a diff could run.
      </EmptyState>
    );
  const rows = changedOnly(run.diff);
  if (rows.length === 0)
    return (
      <EmptyState title="Identical to what clients saw">
        Every mart has the same rows and the same totals as the build before.
      </EmptyState>
    );
  return (
    <Table caption="What changed against the published build">
      <thead>
        <tr>
          <th scope="col">Mart</th>
          <th scope="col" className={ui.num}>
            Rows
          </th>
          <th scope="col" className={ui.num}>
            Added
          </th>
          <th scope="col" className={ui.num}>
            Removed
          </th>
          <th scope="col" className={ui.num}>
            Changed
          </th>
          <th scope="col">Totals that moved</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([mart, d]) => (
          <tr key={mart}>
            <th scope="row" className={styles.mart}>
              {mart}
            </th>
            {d.status ? (
              <td colSpan={5}>{d.status}</td>
            ) : (
              <>
                <td className={ui.num}>
                  {int(d.rows_old)} to {int(d.rows_new)}
                </td>
                <td className={ui.num}>{int(d.added)}</td>
                <td className={ui.num}>{int(d.removed)}</td>
                <td className={ui.num}>{int(d.changed)}</td>
                <td>
                  {Object.entries(d.totals_changed ?? {})
                    .slice(0, 3)
                    .map(([col, t]) => (
                      <div key={col} className={styles.sub}>
                        {col}: {t.old.toLocaleString("en-GB", { maximumFractionDigits: 2 })} to{" "}
                        {t.new.toLocaleString("en-GB", { maximumFractionDigits: 2 })}
                      </div>
                    ))}
                  {(d.columns_added?.length ?? 0) > 0 && (
                    <div className={styles.sub}>new columns: {d.columns_added!.join(", ")}</div>
                  )}
                  {(d.columns_removed?.length ?? 0) > 0 && (
                    <div className={styles.sub}>dropped columns: {d.columns_removed!.join(", ")}</div>
                  )}
                </td>
              </>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function RunPage() {
  const { id = "" } = useParams();
  const run = useRun(id);
  return (
    <QueryView query={run} skeleton={<SkeletonBlock label="Loading the run" rows={6} />}>
      {(r) => {
        const status = RUN_STATUS[r.status];
        const onlyDrift =
          r.status === "blocked" &&
          r.gates.filter((g) => !g.passed && g.severity === "block").every((g) => g.name === "nav_drift");
        return (
          <>
            <p className={styles.crumb}>
              <Link to="/runs">Runs</Link>
            </p>
            <PageHeader
              title={`Run ${r.run_id}`}
              lead={
                <>
                  Started {time(r.started_at)}, finished {time(r.finished_at)}. Built into{" "}
                  <code>{r.build_schema}</code> with figures as of {r.as_of}.
                </>
              }
              actions={<Tag tone={status?.tone ?? "quiet"}>{status?.label ?? humanise(r.status)}</Tag>}
            />
            <div className={styles.page}>
              {r.approved_by && (
                <Notice>
                  Published after review by {r.approved_by}: {r.approval_note}
                </Notice>
              )}
              {onlyDrift && (
                <Notice>
                  Only the drift gate stopped this build. If the move is real, a second person can publish it
                  with <code>pmd approve {r.run_id} --note "…"</code>; tests must have passed.
                </Notice>
              )}
              <Section title="Gates">
                <Gates run={r} />
              </Section>
              <Section
                title="What changed"
                lead="Mart by mart against the build clients saw before. Reviewed before trusting a change to the models."
              >
                <Diff run={r} />
              </Section>
            </div>
          </>
        );
      }}
    </QueryView>
  );
}
