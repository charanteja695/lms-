import type { IsoDateTime } from "@/core/api/types";

/** Mirrors ai-gateway's schemas (lms-backend/ai-gateway/docs/API.md). Money is integer US cents. */
export interface Quota {
  organization_id: string;
  monthly_token_limit: number;
  monthly_request_limit: number;
  monthly_budget_cents: number;
  enabled: boolean;
  is_default: boolean;
}

export interface QuotaBody {
  monthly_token_limit: number | null;
  monthly_request_limit: number | null;
  monthly_budget_cents: number | null;
  enabled: boolean;
}

export interface Usage {
  organization_id: string;
  period: string;
  requests_used: number;
  prompt_tokens_used: number;
  completion_tokens_used: number;
  cost_cents_used: number;
  token_limit: number;
  request_limit: number;
  budget_cents: number;
}

export type Capability = "chat" | "embedding";

export interface RouteEntry {
  provider: string;
  model: string;
}

export type ModelRoutes = Record<Capability, RouteEntry[]>;

export interface Prompt {
  prompt_id: string;
  key: string;
  capability: Capability;
  owner_service: string;
  description: string;
  created_by: string;
  created_at: IsoDateTime;
}

export type PromptStatus = "draft" | "active" | "retired";

export interface PromptVersion {
  version_id: string;
  version: number;
  template: string;
  variables: string[];
  allowed_tools: string[];
  model_params: Record<string, unknown>;
  status: PromptStatus;
  created_by: string;
  activated_by: string | null;
  retired_by: string | null;
  created_at: IsoDateTime;
}

export interface CallLog {
  call_id: string;
  organization_id: string;
  service: string;
  user_id: string | null;
  capability: string;
  prompt_key: string | null;
  prompt_version: number | null;
  provider: string | null;
  model: string | null;
  request_redacted: Record<string, unknown>;
  response_preview: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cost_cents: number;
  latency_ms: number;
  status: string;
  error_code: string | null;
  guardrail_flags: string[];
  created_at: IsoDateTime;
}
