import { Link, useSearchParams } from "react-router-dom";

import type { FundNav } from "../../shared/api/types";
import { date, multiple } from "../../shared/lib/format";
import {
  Amount,
  EmptyState,
  PageHeader,
  QueryView,
  Section,
  SkeletonBlock,
  Table,
  Tag,
  ui,
} from "../../shared/ui";
import { Segmented } from "../../shared/ui/Segmented";
import { FEEDER_LABEL } from "../../shared/theme/tokens";
import { useFunds } from "./api";
import styles from "./Funds.module.css";

const FEEDERS = [
  { value: "", label: "All feeders" },
  ...Object.entries(FEEDER_LABEL).map(([value, label]) => ({ value, label })),
];

function FundTable({ rows }: { rows: FundNav[] }) {
  return (
    <Table caption={`Target funds of ${FEEDER_LABEL[rows[0]!.feeder] ?? rows[0]!.feeder}`}>
      <thead>
        <tr>
          <th scope="col">Fund</th>
          <th scope="col">Strategy</th>
          <th scope="col">Latest quarter</th>
          <th scope="col" className={ui.num}>
            NAV
          </th>
          <th scope="col" className={ui.num}>
            In EUR
          </th>
          <th scope="col" className={ui.num}>
            TVPI
          </th>
          <th scope="col">Statements</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((f) => {
          const est = f.nav_source === "estimated";
          return (
            <tr key={f.fund}>
              <td>
                <Link to={`/funds/${f.fund}`} className={styles.fundLink}>
                  {f.fund_name}
                </Link>
                <div className={styles.sub}>{f.gp}</div>
              </td>
              <td>
                {f.strategy}
                <div className={styles.sub}>{f.region}</div>
              </td>
              <td>{date(f.quarter_end)}</td>
              <td className={ui.num}>
                <Amount
                  value={f.nav_ccy}
                  currency={f.currency}
                  source={est ? "estimated" : "reported"}
                  title={f.estimate_reason ?? undefined}
                />
              </td>
              <td className={ui.num}>
                <Amount value={f.nav_eur} source={est ? "estimated" : "reported"} />
              </td>
              <td className={ui.num}>{multiple(f.tvpi)}</td>
              <td>
                {est ? (
                  <Tag
                    tone="estimate"
                    title={f.estimated_from ? `carried forward from ${date(f.estimated_from)}` : undefined}
                  >
                    {f.estimate_reason ?? "estimated"}
                  </Tag>
                ) : (
                  <Tag tone="good">Reported</Tag>
                )}
                {(f.restatements ?? 0) > 0 && (
                  <div className={styles.sub}>
                    restated {f.restatements} {f.restatements === 1 ? "time" : "times"}
                  </div>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

export function FundsPage() {
  const [params, setParams] = useSearchParams();
  const feeder = params.get("feeder") ?? "";
  const funds = useFunds();
  return (
    <>
      <PageHeader
        title="Target funds"
        lead="The funds the feeders invest in, at their latest quarter. A late or held statement is carried forward from bank flows and marked as an estimate."
        actions={
          <Segmented
            label="Feeder"
            options={FEEDERS}
            value={feeder}
            onChange={(v) => setParams(v ? { feeder: v } : {}, { replace: true })}
          />
        }
      />
      <QueryView
        query={funds}
        skeleton={<SkeletonBlock label="Loading the funds" rows={6} />}
        isEmpty={(r) => r.length === 0}
        empty={
          <EmptyState title="No funds yet">
            The fund list arrives with the first operations file; run <code>pmd run</code>.
          </EmptyState>
        }
      >
        {(rows) => {
          const shown = rows.filter((r) => !feeder || r.feeder === feeder);
          const groups = [...new Set(shown.map((r) => r.feeder))];
          if (groups.length === 0)
            return (
              <EmptyState title="This feeder has no target funds">Pick another feeder above.</EmptyState>
            );
          return (
            <div className={styles.groups}>
              {groups.map((g) => (
                <Section key={g} title={FEEDER_LABEL[g] ?? g}>
                  <FundTable rows={shown.filter((r) => r.feeder === g)} />
                </Section>
              ))}
            </div>
          );
        }}
      </QueryView>
    </>
  );
}
