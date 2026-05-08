import { create } from "zustand";

type UiState = {
  inspectorRequestId: string | null;
  setInspectorRequestId: (id: string | null) => void;
  simulateEnv: boolean;
  setSimulateEnv: (v: boolean) => void;
};

export const useUiStore = create<UiState>((set) => ({
  inspectorRequestId: null,
  setInspectorRequestId: (id) => set({ inspectorRequestId: id }),
  simulateEnv: false,
  setSimulateEnv: (v) => set({ simulateEnv: v }),
}));
