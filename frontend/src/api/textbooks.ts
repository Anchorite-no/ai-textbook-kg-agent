/** Textbooks adapter（plan 17 §4）。
 *  UI 只用本文件导出的接口，不直接 import live/mock。 */

import { apiMode } from "./registry";
import * as live from "./textbooks.live";
import * as mock from "./textbooks.mock";

const impl = apiMode.textbooks === "live" ? live : mock;

export const textbooksApi = {
  listTextbooks: impl.listTextbooks,
  uploadTextbook: impl.uploadTextbook,
  uploadTextbookAsync: impl.uploadTextbookAsync,
  parseTextbook: impl.parseTextbook,
  parseTextbookAsync: impl.parseTextbookAsync,
  getTextbook: impl.getTextbook
};
