/** TanStack Query hook 包装。组件层调本文件，不直接调 textbooksApi。 */

import { useQuery } from "@tanstack/react-query";
import { textbooksApi } from "@/api/textbooks";

export function useTextbooksQuery() {
  return useQuery({
    queryKey: ["textbooks"],
    queryFn: textbooksApi.listTextbooks,
    staleTime: 10_000
  });
}
