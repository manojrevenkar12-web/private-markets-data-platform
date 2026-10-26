import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { Break } from "../../shared/api/types";

export interface BreakFilter {
  owner?: string;
  kind?: string;
  status: "open" | "resolved" | "all";
}

export function breaksPath(f: BreakFilter) {
  const p = new URLSearchParams();
  if (f.kind) p.set("kind", f.kind);
  if (f.owner) p.set("owner", f.owner);
  p.set("status", f.status);
  return `/api/breaks?${p.toString()}`;
}

export const useBreaks = (f: BreakFilter) =>
  useQuery({
    queryKey: ["breaks", f],
    queryFn: () => api.get<Break[]>(breaksPath(f)),
    placeholderData: (x) => x,
  });

export type BreakActionKind = "resolve" | "reopen" | "note";

export function useBreakAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, note }: { id: string; action: BreakActionKind; note: string }) =>
      api.post<Break>(`/api/breaks/${id}/actions`, { action, note }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["breaks"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
      void qc.invalidateQueries({ queryKey: ["client"] });
    },
  });
}
