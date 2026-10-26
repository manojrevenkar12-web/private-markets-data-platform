import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { ClientDetail, ClientRow, Identity } from "../../shared/api/types";

export const PAGE = 25;

export function clientsPath(q: string, feeder: string, page: number) {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (feeder) p.set("feeder", feeder);
  p.set("limit", String(PAGE));
  p.set("offset", String(page * PAGE));
  return `/api/clients?${p.toString()}`;
}

export const useClients = (q: string, feeder: string, page: number) =>
  useQuery({
    queryKey: ["clients", q, feeder, page],
    queryFn: () => api.get<{ total: number; rows: ClientRow[] }>(clientsPath(q, feeder, page)),
    placeholderData: (x) => x,
  });

export const useClient = (key: string) =>
  useQuery({
    queryKey: ["client", key],
    queryFn: () => api.get<ClientDetail>(`/api/clients/${encodeURIComponent(key)}`),
  });

/** Who a client is. Operations only, with a reason; the API logs every attempt, granted or not. */
export const useReveal = (key: string) =>
  useMutation({
    mutationFn: (reason: string) =>
      api.post<Identity>(`/api/clients/${encodeURIComponent(key)}/reveal`, { reason }),
  });
