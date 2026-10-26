/** API answers captured from a real run (`pmd-sim`, `pmd run` twice, PMD_TODAY=2026-10-26). */
import type {
  Break,
  CashCall,
  ClientDetail,
  ClientRow,
  FundDetail,
  FundNav,
  Freshness,
  Lineage,
  Overview,
  Run,
} from "../src/shared/api/types";
import breaks from "./fixtures/breaks.json";
import cash from "./fixtures/cash.json";
import client from "./fixtures/client.json";
import clients from "./fixtures/clients.json";
import freshness from "./fixtures/freshness.json";
import fund from "./fixtures/fund.json";
import funds from "./fixtures/funds.json";
import health from "./fixtures/health.json";
import lineage from "./fixtures/lineage.json";
import overview from "./fixtures/overview.json";
import run from "./fixtures/run.json";
import runs from "./fixtures/runs.json";
import type { Routes } from "./harness";

export const fx = {
  breaks: breaks as Break[],
  cash: cash as CashCall[],
  client: client as unknown as ClientDetail,
  clients: clients as { total: number; rows: ClientRow[] },
  freshness: freshness as unknown as Freshness,
  fund: fund as unknown as FundDetail,
  funds: funds as unknown as FundNav[],
  health,
  lineage: lineage as Lineage,
  overview: overview as unknown as Overview,
  run: run as unknown as Run,
  runs: runs as unknown as Run[],
};

/** The fund as known on a day: the versions received by then, as the API computes it. */
export function fundKnownAt(day: string): FundDetail {
  const f = JSON.parse(JSON.stringify(fx.fund)) as FundDetail;
  f.known_at = day;
  f.as_known = f.versions.filter(
    (v) => v.known_from <= day && (v.known_until == null || v.known_until > day),
  );
  return f;
}

export function routes(): Routes {
  return {
    "GET /api/health": fx.health,
    "GET /api/overview": fx.overview,
    "GET /api/runs": fx.runs,
    [`GET /api/runs/${fx.run.run_id}`]: fx.run,
    "GET /api/freshness": fx.freshness,
    "GET /api/breaks": fx.breaks,
    "GET /api/cash": fx.cash,
    "GET /api/funds": fx.funds,
    "GET /api/funds/KES4": (url: string) => {
      const day = new URL(url, "http://x").searchParams.get("known_at");
      return day ? fundKnownAt(day) : fx.fund;
    },
    "GET /api/clients": fx.clients,
    [`GET /api/clients/${fx.client.client.client_key}`]: fx.client,
    "GET /api/lineage": fx.lineage,
  };
}
