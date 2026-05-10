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
const GRAPH_TOP_N_DEFAULT = 1000;

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
  workflowUseLLM: boolean;

  // ---- 非持久化 ----
  selectedTextbookId: string | null;
  selectedNodeId: string | null;
  nodeDetailOpen: boolean;
  selectedDecisionId: string | null;
  graphMode: GraphMode;
  searchKeyword: string;
  relationFilters: string[];
  reportGenerateTick: number;

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
  setWorkflowUseLLM: (enabled: boolean) => void;
  setSelectedTextbookId: (id: string | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  closeNodeDetail: () => void;
  setSelectedDecisionId: (id: string | null) => void;
  setSearchKeyword: (k: string) => void;
  setRelationFilters: (filters: string[]) => void;
  requestReportGenerate: () => void;
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
      graphTopN: GRAPH_TOP_N_DEFAULT,
      workflowUseLLM: false,

      selectedTextbookId: null,
      selectedNodeId: null,
      nodeDetailOpen: false,
      selectedDecisionId: null,
      graphMode: "single",
      searchKeyword: "",
      relationFilters: [],
      reportGenerateTick: 0,

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
      setGraphTopN: (graphTopN) => set({ graphTopN: clamp(graphTopN, 50, 1000) }),
      setWorkflowUseLLM: (workflowUseLLM) => set({ workflowUseLLM }),
      setSelectedTextbookId: (selectedTextbookId) => set({ selectedTextbookId }),
      setSelectedNodeId: (selectedNodeId) =>
        set(selectedNodeId
          ? { selectedNodeId, nodeDetailOpen: true, rightHidden: false }
          : { selectedNodeId: null, nodeDetailOpen: false }),
      closeNodeDetail: () => set({ selectedNodeId: null, nodeDetailOpen: false }),
      setSelectedDecisionId: (selectedDecisionId) => set({ selectedDecisionId }),
      setSearchKeyword: (searchKeyword) => set({ searchKeyword }),
      setRelationFilters: (relationFilters) => set({ relationFilters }),
      requestReportGenerate: () => set((s) => ({ reportGenerateTick: s.reportGenerateTick + 1 }))
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
        graphTopN: state.graphTopN,
        workflowUseLLM: state.workflowUseLLM
      }),
      version: 2,
      onRehydrateStorage: () => (state) => {
        if (state?.theme) {
          document.documentElement.setAttribute("data-theme", state.theme);
        }
      }
    }
  )
);
