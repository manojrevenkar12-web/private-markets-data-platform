import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { Lineage } from "../../shared/api/types";

export const useLineage = () =>
  useQuery({ queryKey: ["lineage"], queryFn: () => api.get<Lineage>("/api/lineage"), staleTime: Infinity });
