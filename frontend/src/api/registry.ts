/** 各域 API 的 live / mock 切换。env 变量在 .env.development。
 *  用 import.meta.env.MODE 防止生产构建里 mock。 */

type Mode = "live" | "mock";

const isProd = import.meta.env.PROD;

function pick(envValue: string | undefined, fallback: Mode): Mode {
  if (isProd) return "live";
  if (envValue === "mock" || envValue === "live") return envValue;
  return fallback;
}

export const apiMode = {
  textbooks: pick(import.meta.env.VITE_API_TEXTBOOKS, "live"),
  graph: pick(import.meta.env.VITE_API_GRAPH, "live"),
  integration: pick(import.meta.env.VITE_API_INTEGRATION, "live"),
  rag: pick(import.meta.env.VITE_API_RAG, "live"),
  dialogue: pick(import.meta.env.VITE_API_DIALOGUE, "live"),
  report: pick(import.meta.env.VITE_API_REPORT, "live")
} as const;

export type ApiDomain = keyof typeof apiMode;
