/** 全局 UI 状态。plan 16 §7.2。
 *  持久化白名单见 partialize，非持久化字段不会写入 localStorage。 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type RightTab = "integration" | "rag" | "dialogue" | "report";
export type GraphMode = "single" | "merged" | "compare";
export type Theme = "light" | "dark";

const PERSIST_KEY = "kfa-ui-v1";

const LEFT_DEFAULT = 320;
const LEFT_MIN = 240;
const LEFT_MAX = 480;
const LEFT_COLLAPSED = 56;

const RIGHT_DEFAULT = 420;
const RIGHT_MIN = 360;
const RIGHT_MAX = 560;

export const layoutLimits = {
  leftDefault: LEFT_DEFAULT,
  leftMin: LEFT_MIN,
  leftMax: LEFT_MAX,
  leftCollapsed: LEFT_COLLAPSED,
  rightDefault: RIGHT_DEFAULT,
  rightMin: RIGHT_MIN,
  rightMax: RIGHT_MAX
} as const;

export interface UIState {
  // ---- 持久化 ----
  leftWidth: number;
  rightWidth: number;
  leftCollapsed: boolean;
  rightHidden: boolean;
  activeRightTab: RightTab;
  theme: Theme;
  graphTopN: number;

  // ---- 非持久化 ----
  selectedTextbookId: string | null;
  selectedNodeId: string | null;
  selectedDecisionId: string | null;
  graphMode: GraphMode;
  searchKeyword: string;
  relationFilters: string[];

  // ---- actions ----
  setLeftWidth: (w: number) => void;
  setRightWidth: (w: number) => void;
  resetLeftWidth: () => void;
  resetRightWidth: () => void;
  toggleLeftCollapsed: () => void;
  toggleRightHidden: () => void;
  setActiveRightTab: (t: RightTab) => void;
  setTheme: (t: Theme) => void;
  setGraphMode: (m: GraphMode) => void;
  setGraphTopN: (n: number) => void;
  setSelectedTextbookId: (id: string | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setSelectedDecisionId: (id: string | null) => void;
  setSearchKeyword: (k: string) => void;
  setRelationFilters: (filters: string[]) => void;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      leftWidth: LEFT_DEFAULT,
      rightWidth: RIGHT_DEFAULT,
      leftCollapsed: false,
      rightHidden: false,
      activeRightTab: "integration",
      theme: "light",
      graphTopN: 200,

      selectedTextbookId: null,
      selectedNodeId: null,
      selectedDecisionId: null,
      graphMode: "single",
      searchKeyword: "",
      relationFilters: [],

      setLeftWidth: (w) => set({ leftWidth: clamp(w, LEFT_MIN, LEFT_MAX) }),
      setRightWidth: (w) => set({ rightWidth: clamp(w, RIGHT_MIN, RIGHT_MAX) }),
      resetLeftWidth: () => set({ leftWidth: LEFT_DEFAULT }),
      resetRightWidth: () => set({ rightWidth: RIGHT_DEFAULT }),
      toggleLeftCollapsed: () => set((s) => ({ leftCollapsed: !s.leftCollapsed })),
      toggleRightHidden: () => set((s) => ({ rightHidden: !s.rightHidden })),
      setActiveRightTab: (activeRightTab) => set({ activeRightTab }),
      setTheme: (theme) => {
        document.documentElement.setAttribute("data-theme", theme);
        set({ theme });
      },
      setGraphMode: (graphMode) => set({ graphMode }),
      setGraphTopN: (graphTopN) => set({ graphTopN }),
      setSelectedTextbookId: (selectedTextbookId) => set({ selectedTextbookId }),
      setSelectedNodeId: (selectedNodeId) => set({ selectedNodeId }),
      setSelectedDecisionId: (selectedDecisionId) => set({ selectedDecisionId }),
      setSearchKeyword: (searchKeyword) => set({ searchKeyword }),
      setRelationFilters: (relationFilters) => set({ relationFilters })
    }),
    {
      name: PERSIST_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        leftWidth: state.leftWidth,
        rightWidth: state.rightWidth,
        leftCollapsed: state.leftCollapsed,
        rightHidden: state.rightHidden,
        activeRightTab: state.activeRightTab,
        theme: state.theme,
        graphTopN: state.graphTopN
      }),
      version: 1,
      onRehydrateStorage: () => (state) => {
        if (state?.theme) {
          document.documentElement.setAttribute("data-theme", state.theme);
        }
      }
    }
  )
);
