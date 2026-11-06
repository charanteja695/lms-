import { configureStore, createListenerMiddleware, isAnyOf } from "@reduxjs/toolkit";

import { baseApi } from "@/core/api/baseApi";
import { storage } from "@/core/lib/storage";
import toastReducer from "@/core/toast/toastSlice";
import authReducer, { credentialsReceived, loggedOut, userFlagsChanged } from "@/modules/user-management/auth/store/authSlice";

const persistence = createListenerMiddleware();

export const store = configureStore({
  reducer: {
    auth: authReducer,
    toasts: toastReducer,
    [baseApi.reducerPath]: baseApi.reducer,
  },
  middleware: (getDefault) => getDefault().prepend(persistence.middleware).concat(baseApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

persistence.startListening({
  matcher: isAnyOf(credentialsReceived, userFlagsChanged, loggedOut),
  effect: (action, api) => {
    const { auth } = api.getState() as RootState;
    storage.writeSession(auth.user ? { user: auth.user, token: auth.accessToken ?? undefined } : null);
    // Never show one person's cached data to the next person on this device.
    if (loggedOut.match(action)) api.dispatch(baseApi.util.resetApiState());
  },
});
