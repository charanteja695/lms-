import { createSlice, nanoid, type PayloadAction } from "@reduxjs/toolkit";

export type ToastTone = "success" | "error" | "info";

export interface Toast {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
}

const toastSlice = createSlice({
  name: "toasts",
  initialState: [] as Toast[],
  reducers: {
    toastAdded: {
      reducer(state, action: PayloadAction<Toast>) {
        state.push(action.payload);
        if (state.length > 4) state.shift();
      },
      prepare(toast: Omit<Toast, "id">) {
        return { payload: { ...toast, id: nanoid() } };
      },
    },
    toastDismissed(state, action: PayloadAction<string>) {
      return state.filter((toast) => toast.id !== action.payload);
    },
  },
});

export const { toastAdded, toastDismissed } = toastSlice.actions;
export default toastSlice.reducer;
