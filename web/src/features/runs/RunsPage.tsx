import { Link } from "react-router-dom";

import { int, time } from "../../shared/lib/format";
import { EmptyState, PageHeader, QueryView, SkeletonBlock, Table, Tag, ui } from "../../shared/ui";
import { RUN_STATUS } from "../../shared/theme/tokens";
import { useRuns } from "../today/api";
import styles from "./Runs.module.css";

export function RunsPage() {
  const runs = useRuns(50);
  return (
    <>
      <PageHeader
        title="Runs"
        lead="Every run loads the sources, builds the warehouse into its own schema, runs the gates and publishes only if none stops it."
      />
      <QueryView
        query={runs}
        skeleton={<SkeletonBlock label="Loading the runs" rows={8} />}
        isEmpty={(r) => r.length === 0}
        empty={
          <EmptyState title="No runs yet">
            Start one with <code>pmd run</code>.
          </EmptyState>
        }
      >
        {(rows) => (
          <Table caption="Runs">
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Started</th>
                <th scope="col">Status</th>
                <th scope="col">Gates</th>
                <th scope="col" className={ui.num}>
                  Open breaks
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const failed = r.gates.filter((g) => !g.passed);
                const blocking = failed.filter((g) => g.severity === "block");
                return (
                  <tr key={r.run_id}>
                    <td>
                      <Link to={`/runs/${r.run_id}`} className={styles.runId}>
                        {r.run_id}
                      </Link>
                      {r.approved_by && <div className={styles.sub}>approved by {r.approved_by}</div>}
                    </td>
                    <td>{time(r.started_at)}</td>
                    <td>
                      <Tag tone={RUN_STATUS[r.status]?.tone ?? "quiet"}>
                        {RUN_STATUS[r.status]?.label ?? r.status}
                      </Tag>
                    </td>
                    <td>
                      {failed.length === 0
                        ? `all ${r.gates.length} passed`
                        : blocking.length > 0
                          ? `stopped by ${blocking.map((g) => g.name.replace(/_/g, " ")).join(", ")}`
                          : `${failed.length} warned`}
                    </td>
                    <td className={ui.num}>
                      {r.counts?.["recon_breaks"] != null ? int(r.counts["recon_breaks"]) : "n/a"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </QueryView>
    </>
  );
}
