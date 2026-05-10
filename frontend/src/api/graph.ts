/** Graph adapter barrel。按 plan 17 §4：UI 通过本文件调用，不直接 import live/mock。 */

import { apiMode } from "./registry";
import * as live from "./graph.live";
import * as mock from "./graph.mock";

const impl = apiMode.graph === "live" ? live : mock;

export const graphApi = {
  fetchGraph: (options?: live.FetchGraphOptions) =>
    apiMode.graph === "live"
      ? live.fetchGraph(options)
      : mock.fetchGraph(options?.mode ?? "single"),
  fetchNode: impl.fetchNode,
  buildGraph: impl.buildGraph,
  buildLayeredKG: impl.buildLayeredKG,
  getLayeredKG: impl.getLayeredKG
};

export type { GraphPayloadMock as GraphPayload } from "./graph.mock";
