import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { Overview, Run } from "../../shared/api/types";

export const useOverview = () =>
  useQuery({ queryKey: ["overview"], queryFn: () => api.get<Overview>("/api/overview") });

/** The newest runs first; the ribbon shows them oldest to newest. */
export const useRuns = (limit = 20) =>
  useQuery({ queryKey: ["runs", limit], queryFn: () => api.get<Run[]>(`/api/runs?limit=${limit}`) });
