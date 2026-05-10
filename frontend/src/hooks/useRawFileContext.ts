import { useMemo } from "react";
import { useUIStore } from "@/store/uiStore";
import { useSevenBooksDatasetQuery, useTextbooksQuery } from "@/hooks/useTextbooks";

export function useRawFileContext() {
  const selectedTextbookId = useUIStore((s) => s.selectedTextbookId);
  const dataset = useSevenBooksDatasetQuery();
  const textbooks = useTextbooksQuery();

  const rawFileIds = useMemo(() => {
    if (dataset.data?.raw_file_ids?.length) return dataset.data.raw_file_ids;
    return textbooks.data?.map((item) => item.raw_file_id) ?? [];
  }, [dataset.data?.raw_file_ids, textbooks.data]);

  const activeRawFileIds = useMemo(() => {
    if (selectedTextbookId) return [selectedTextbookId];
    return rawFileIds;
  }, [rawFileIds, selectedTextbookId]);

  return {
    selectedTextbookId,
    rawFileIds,
    activeRawFileIds,
    dataset: dataset.data,
    datasetQuery: dataset,
    textbooks: textbooks.data ?? [],
    textbooksQuery: textbooks
  };
}
