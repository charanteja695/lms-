import { Id, IsoDateTime, SuccessEnvelope } from "@/core/api/types";
import { AdminScope, InstitutionRef, Role } from "@/modules/user-management/common/types";

export interface TokenOut {
  access_token: string;
  /** Null for browser sessions: the refresh token is set as an httpOnly cookie instead. */
  refresh_token: string | null;
  token_type: "Bearer";
  expires_in: number;
  refresh_expires_in: number;
}

export interface AuthUser {
  user_id: Id;
  full_name: string;
  email: string;
  username: string;
  role: Role;
  institution: InstitutionRef | null;
  scopes: AdminScope[];
  must_change_password: boolean;
  mfa_enabled: boolean;
  mfa_setup_required: boolean;
}

export interface MfaChallenge {
  mfa_token: string;
  expires_in: number;
  methods: string[];
}

export interface LoginResponse extends SuccessEnvelope {
  token: TokenOut | null;
  user: AuthUser | null;
  mfa_challenge: MfaChallenge | null;
}

export interface SessionOut {
  session_id: Id;
  is_current: boolean;
  ip_address: string | null;
  user_agent: string | null;
  created_time: IsoDateTime;
  last_active_time: IsoDateTime;
  expires_time: IsoDateTime;
}

export interface MfaStatus {
  enabled: boolean;
  required: boolean;
  recovery_codes_remaining: number;
}
