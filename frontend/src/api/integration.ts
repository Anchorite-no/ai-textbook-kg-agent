import { apiMode } from "./registry";
import * as live from "./integration.live";
import * as mock from "./integration.mock";

const impl = apiMode.integration === "live" ? live : mock;

export const integrationApi = {
  getIntegration: impl.getIntegration,
  buildIntegration: impl.buildIntegration
};
