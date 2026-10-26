import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { FundDetail, FundNav } from "../../shared/api/types";

export const useFunds = () =>
  useQuery({ queryKey: ["funds"], queryFn: () => api.get<FundNav[]>("/api/funds") });

export const useFund = (fund: string, knownAt?: string) =>
  useQuery({
    queryKey: ["fund", fund, knownAt ?? null],
    queryFn: () =>
      api.get<FundDetail>(`/api/funds/${encodeURIComponent(fund)}${knownAt ? `?known_at=${knownAt}` : ""}`),
    placeholderData: (prev, prevQuery) => (prevQuery?.queryKey[1] === fund ? prev : undefined),
  });
