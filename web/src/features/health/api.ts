import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { Freshness } from "../../shared/api/types";

export const useFreshness = () =>
  useQuery({ queryKey: ["freshness"], queryFn: () => api.get<Freshness>("/api/freshness") });

export interface Released {
  file_id: number;
  released_by: string;
  takes_effect: string;
}

/** Fund accounting releases a held statement; the next run uses it. */
export function useRelease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ fileId, note }: { fileId: number; note: string }) =>
      api.post<Released>(`/api/statements/${fileId}/release`, { note }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freshness"] }),
  });
}
