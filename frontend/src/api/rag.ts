import { apiMode } from "./registry";
import * as live from "./rag.live";
import * as mock from "./rag.mock";

const impl = apiMode.rag === "live" ? live : mock;

export const ragApi = {
  indexRAG: impl.indexRAG,
  getRAGStatus: impl.getRAGStatus,
  queryRAG: impl.queryRAG
};
