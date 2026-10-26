import { Route, Routes } from "react-router-dom";

import { BreaksPage } from "../features/breaks/BreaksPage";
import { ClientPage } from "../features/clients/ClientPage";
import { ClientsPage } from "../features/clients/ClientsPage";
import { FundPage } from "../features/funds/FundPage";
import { FundsPage } from "../features/funds/FundsPage";
import { HealthPage } from "../features/health/HealthPage";
import { LineagePage } from "../features/lineage/LineagePage";
import { RunPage } from "../features/runs/RunPage";
import { RunsPage } from "../features/runs/RunsPage";
import { TodayPage } from "../features/today/TodayPage";
import { EmptyState } from "../shared/ui";
import { Shell } from "./Shell";

function NotFound() {
  return (
    <EmptyState title="There is nothing at this address">
      Use the menu above, or start from today's numbers.
    </EmptyState>
  );
}

export function AppRoutes() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<TodayPage />} />
        <Route path="/breaks" element={<BreaksPage />} />
        <Route path="/funds" element={<FundsPage />} />
        <Route path="/funds/:fund" element={<FundPage />} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/clients/:key" element={<ClientPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:id" element={<RunPage />} />
        <Route path="/lineage" element={<LineagePage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Shell>
  );
}
