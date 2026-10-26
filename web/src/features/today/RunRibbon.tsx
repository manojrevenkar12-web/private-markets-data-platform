import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import type { Gate, Run } from "../../shared/api/types";
import { time } from "../../shared/lib/format";
import { GATES, MOTION, RUN_STATUS } from "../../shared/theme/tokens";
import styles from "./RunRibbon.module.css";

type CellState = "pass" | "warn" | "block" | "skipped";

function cellState(g: Gate | undefined): CellState {
  if (!g) return "skipped";
  if (g.passed) return "pass";
  return g.severity === "block" ? "block" : "warn";
}

const WORD: Record<CellState, string> = {
  pass: "passed",
  warn: "warned",
  block: "stopped the publish",
  skipped: "did not run",
};

/**
 * Every run as one column of gates, oldest on the left. A build reaches clients only when no gate in its column
 * is solid red; the column clients see now is marked underneath. Read as a table: gates are rows, runs columns.
 */
export function RunRibbon({ runs, published }: { runs: Run[]; published: string | null }) {
  const ordered = [...runs].reverse();
  return (
    <div className={styles.wrap} role="region" aria-label="Gates of the last runs" tabIndex={0}>
      <table className={styles.ribbon}>
        <caption className="visually-hidden">
          Gates of the last {ordered.length} runs, oldest first. The published run is the one clients see.
        </caption>
        <thead>
          <tr>
            <th scope="col" className={styles.corner}>
              <span className="visually-hidden">Gate</span>
            </th>
            {ordered.map((r) => (
              <th key={r.run_id} scope="col" className={styles.runHead}>
                <Link to={`/runs/${r.run_id}`} className={styles.runLink} title={`Run ${r.run_id}`}>
                  <span className="visually-hidden">
                    Run {r.run_id}, {RUN_STATUS[r.status]?.label ?? r.status}
                  </span>
                  <span aria-hidden className={`${styles.status} ${styles[r.status] ?? ""}`} />
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {GATES.map((gate, row) => (
            <tr key={gate.name}>
              <th scope="row" className={styles.gateName} title={gate.means}>
                {gate.label}
              </th>
              {ordered.map((r, col) => {
                const g = r.gates.find((x) => x.name === gate.name);
                const state = cellState(g);
                return (
                  <td key={r.run_id} className={styles.cellBox}>
                    <motion.span
                      className={`${styles.cell} ${styles[state]}`}
                      title={g ? `${gate.label}: ${g.detail}` : `${gate.label}: did not run`}
                      initial={{ scaleY: 0 }}
                      animate={{ scaleY: 1 }}
                      transition={{
                        duration: MOTION.move,
                        ease: MOTION.ease,
                        delay: col * MOTION.stagger + row * MOTION.stagger * 0.5,
                      }}
                    />
                    <span className="visually-hidden">{WORD[state]}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" className={styles.gateName}>
              Clients see
            </th>
            {ordered.map((r) => (
              <td key={r.run_id} className={styles.cellBox}>
                {r.run_id === published ? (
                  <span className={styles.live}>
                    <span aria-hidden className={styles.flag} />
                    <span className="visually-hidden">this run</span>
                  </span>
                ) : null}
              </td>
            ))}
          </tr>
        </tfoot>
      </table>
      <p className={styles.span}>
        {ordered.length > 0 && (
          <>
            {time(ordered[0]?.started_at)} to {time(ordered[ordered.length - 1]?.started_at)}
          </>
        )}
      </p>
    </div>
  );
}

export function RibbonLegend() {
  return (
    <ul className={styles.legend} aria-label="What the cells mean">
      <li>
        <span aria-hidden className={`${styles.cell} ${styles.pass}`} /> Passed
      </li>
      <li>
        <span aria-hidden className={`${styles.cell} ${styles.warn}`} /> Warned, published anyway
      </li>
      <li>
        <span aria-hidden className={`${styles.cell} ${styles.block}`} /> Stopped the publish
      </li>
      <li>
        <span aria-hidden className={`${styles.cell} ${styles.skipped}`} /> Did not run
      </li>
    </ul>
  );
}
