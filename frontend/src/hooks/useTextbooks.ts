/** TanStack Query hook 包装。组件层调本文件，不直接调 textbooksApi。 */

import { useQuery } from "@tanstack/react-query";
import { textbooksApi } from "@/api/textbooks";
import { datasetsApi } from "@/api/datasets";

export function useTextbooksQuery() {
  return useQuery({
    queryKey: ["textbooks"],
    queryFn: textbooksApi.listTextbooks,
    staleTime: 10_000
  });
}

export function useSevenBooksDatasetQuery() {
  return useQuery({
    queryKey: ["dataset", "seven-books"],
    queryFn: datasetsApi.getSevenBooksDataset,
    staleTime: 15_000
  });
}

export function useTextbookDetailQuery(rawFileId: string | null) {
  return useQuery({
    queryKey: ["textbook", rawFileId],
    queryFn: () => (rawFileId ? textbooksApi.getTextbook(rawFileId) : Promise.resolve(null)),
    enabled: Boolean(rawFileId),
    staleTime: 60_000
  });
}
