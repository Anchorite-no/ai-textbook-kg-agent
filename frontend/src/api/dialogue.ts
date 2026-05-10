import { apiMode } from "./registry";
import * as live from "./dialogue.live";
import * as mock from "./dialogue.mock";

const impl = apiMode.dialogue === "live" ? live : mock;

export const dialogueApi = {
  getHistory: impl.getHistory,
  sendMessage: impl.sendMessage
};
