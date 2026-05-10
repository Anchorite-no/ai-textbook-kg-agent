import { apiMode } from "./registry";
import * as live from "./report.live";
import * as mock from "./report.mock";

const impl = apiMode.report === "mock" ? mock : live;

export const reportApi = {
  generateReport: impl.generateReport
};
