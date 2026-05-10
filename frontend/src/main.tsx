import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider
} from "@tanstack/react-query";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

import App from "./App";
import { ApiError } from "./api/errors";
import { toastStore } from "./components/layout/ToastViewport";
import "./styles/index.css";

const SILENT_EMPTY_STATE_QUERY_CODES = new Set([
  "ALIGNMENT_NOT_FOUND",
  "INTEGRATION_NOT_FOUND"
]);

function reportError(error: unknown, kind: "query" | "mutation") {
  if (error instanceof ApiError) {
    if (kind === "query" && SILENT_EMPTY_STATE_QUERY_CODES.has(error.code)) {
      return;
    }

    toastStore.push({
      tone: "error",
      title: error.message,
      description: error.code !== `HTTP_${error.status}` ? `code: ${error.code}` : undefined
    });
  } else {
    const message = error instanceof Error ? error.message : "未知错误";
    toastStore.push({
      tone: "error",
      title: kind === "query" ? "请求失败" : "操作失败",
      description: message
    });
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1
    },
    mutations: {
      retry: 0
    }
  },
  queryCache: new QueryCache({
    onError: (error) => reportError(error, "query")
  }),
  mutationCache: new MutationCache({
    onError: (error) => reportError(error, "mutation")
  })
});

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("#root not found");

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipPrimitive.Provider delayDuration={400} skipDelayDuration={120}>
        <App />
      </TooltipPrimitive.Provider>
    </QueryClientProvider>
  </StrictMode>
);
