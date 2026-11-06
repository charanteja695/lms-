import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import { storage } from "@/core/lib/storage";
import type { AuthUser, MfaChallenge, TokenOut } from "@/modules/user-management/auth/types";

export interface AuthState {
  /** Kept in memory only; a page reload obtains a new one with the refresh cookie. */
  accessToken: string | null;
  user: AuthUser | null;
  /** "checking" while a stored session is being restored on start-up. */
  sessionStatus: "checking" | "ready";
  mfaChallenge: (MfaChallenge & { identifier: string; receivedAt: number }) | null;
}

const persisted = storage.readSession();

const initialState: AuthState = {
  accessToken: persisted?.token ?? null,
  user: persisted?.user ?? null,
  sessionStatus: persisted?.user ? (persisted.token ? "ready" : "checking") : "ready",
  mfaChallenge: null,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    credentialsReceived(state, action: PayloadAction<{ token: TokenOut; user: AuthUser }>) {
      state.accessToken = action.payload.token.access_token;
      state.user = action.payload.user;
      state.sessionStatus = "ready";
      state.mfaChallenge = null;
    },
    mfaChallengeReceived(state, action: PayloadAction<{ challenge: MfaChallenge; identifier: string }>) {
      state.mfaChallenge = { ...action.payload.challenge, identifier: action.payload.identifier, receivedAt: Date.now() };
    },
    mfaChallengeCleared(state) {
      state.mfaChallenge = null;
    },
    userFlagsChanged(state, action: PayloadAction<Partial<Pick<AuthUser, "must_change_password" | "mfa_setup_required" | "mfa_enabled" | "full_name">>>) {
      if (state.user) Object.assign(state.user, action.payload);
    },
    sessionRestoreFinished(state) {
      state.sessionStatus = "ready";
    },
    loggedOut(state) {
      state.accessToken = null;
      state.user = null;
      state.sessionStatus = "ready";
      state.mfaChallenge = null;
    },
  },
});

export const {
  credentialsReceived,
  mfaChallengeReceived,
  mfaChallengeCleared,
  userFlagsChanged,
  sessionRestoreFinished,
  loggedOut,
} = authSlice.actions;
export default authSlice.reducer;
