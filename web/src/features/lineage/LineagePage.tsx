import { motion } from "framer-motion";
import { useMemo, useState } from "react";

import type { Lineage } from "../../shared/api/types";
import { EmptyState, PageHeader, QueryView, SkeletonBlock } from "../../shared/ui";
import { LAYER, MOTION } from "../../shared/theme/tokens";
import { useLineage } from "./api";
import styles from "./Lineage.module.css";

function walk(start: string, next: Map<string, string[]>) {
  const seen = new Set<string>();
  const todo = [start];
  while (todo.length) {
    const id = todo.pop()!;
    for (const n of next.get(id) ?? []) {
      if (!seen.has(n)) {
        seen.add(n);
        todo.push(n);
      }
    }
  }
  return seen;
}

function Graph({ g }: { g: Lineage }) {
  const [selected, setSelected] = useState<string | null>(null);
  const { up, down, byId } = useMemo(() => {
    const up = new Map<string, string[]>();
    const down = new Map<string, string[]>();
    for (const e of g.edges) {
      up.set(e.to, [...(up.get(e.to) ?? []), e.from]);
      down.set(e.from, [...(down.get(e.from) ?? []), e.to]);
    }
    return { up, down, byId: new Map(g.nodes.map((n) => [n.id, n])) };
  }, [g]);

  const ancestors = selected ? walk(selected, up) : new Set<string>();
  const descendants = selected ? walk(selected, down) : new Set<string>();
  const node = selected ? byId.get(selected) : undefined;
  const layers = Object.entries(LAYER).sort((a, b) => a[1].order - b[1].order);
  const names = (ids: Set<string>) =>
    [...ids].map((i) => byId.get(i)?.name ?? i).sort((a, b) => a.localeCompare(b));

  return (
    <div className={styles.layout}>
      <div className={styles.columns}>
        {layers.map(([layer, meta]) => {
          const nodes = g.nodes.filter((n) => n.layer === layer).sort((a, b) => a.name.localeCompare(b.name));
          return (
            <section key={layer} className={styles.column} aria-labelledby={`layer-${layer}`}>
              <h2 id={`layer-${layer}`}>
                {meta.label} <span className={styles.count}>{nodes.length}</span>
              </h2>
              <ul>
                {nodes.map((n) => {
                  const role =
                    n.id === selected
                      ? "selected"
                      : ancestors.has(n.id)
                        ? "upstream"
                        : descendants.has(n.id)
                          ? "downstream"
                          : selected
                            ? "other"
                            : "idle";
                  return (
                    <li key={n.id}>
                      <motion.button
                        type="button"
                        className={`${styles.node} ${styles[role]}`}
                        aria-pressed={n.id === selected}
                        onClick={() => setSelected(n.id === selected ? null : n.id)}
                        animate={{ opacity: role === "other" ? 0.4 : 1 }}
                        transition={{ duration: MOTION.quick }}
                      >
                        {n.name}
                        {role === "upstream" && (
                          <span className="visually-hidden">, feeds the selected model</span>
                        )}
                        {role === "downstream" && (
                          <span className="visually-hidden">, built from the selected model</span>
                        )}
                      </motion.button>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
      <aside className={styles.detail} aria-live="polite">
        {node ? (
          <>
            <h2>{node.name}</h2>
            <p className={styles.layer}>{LAYER[node.layer]?.label ?? node.layer}</p>
            {node.description && <p>{node.description}</p>}
            <h3>Built from ({ancestors.size})</h3>
            <p className={styles.list}>
              {ancestors.size ? names(ancestors).join(", ") : "nothing: it is a source"}
            </p>
            <h3>Feeds ({descendants.size})</h3>
            <p className={styles.list}>
              {descendants.size ? names(descendants).join(", ") : "nothing: clients and the API read it"}
            </p>
          </>
        ) : (
          <>
            <h2>Pick a model</h2>
            <p>
              Everything it is built from and everything built from it lights up. The graph comes from dbt's
              manifest of the published build.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}

export function LineagePage() {
  const lineage = useLineage();
  return (
    <>
      <PageHeader
        title="Lineage"
        lead="From each raw source to the marts clients and the API read, as dbt built them."
      />
      <QueryView
        query={lineage}
        skeleton={<SkeletonBlock label="Loading the lineage" rows={4} height="12rem" />}
        isEmpty={(g) => g.nodes.length === 0}
        empty={
          <EmptyState title="No models yet">
            Run <code>pmd run</code> to build the warehouse.
          </EmptyState>
        }
      >
        {(g) => <Graph g={g} />}
      </QueryView>
    </>
  );
}
