import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { Run } from "../../shared/api/types";

export const useRun = (id: string) =>
  useQuery({ queryKey: ["run", id], queryFn: () => api.get<Run>(`/api/runs/${encodeURIComponent(id)}`) });
