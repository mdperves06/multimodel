export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  capability: string;
  max_outputs_per_request: number;
  sizes: string[];
  default_size: string | null;
  qualities: string[];
}

export interface Provider {
  slug: string;
  name: string;
  capabilities: string[];
  models: ModelInfo[];
  supports_usage_api: boolean;
}

export type RateLimits = Record<string, number | string | null>;

export interface Account {
  id: string;
  provider: string;
  provider_name: string;
  label: string;
  status: "active" | "invalid" | "disabled";
  available: boolean;
  capabilities: string[];
  models: ModelInfo[];
  credential_hint: string;
  rate_limited_until: string | null;
  last_request_at: string | null;
  last_validated_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  limits: RateLimits | null;
  created_at: string;
}

export interface AccountTestResult {
  ok: boolean;
  message: string;
  account: Account;
}

export type JobStatus =
  | "queued"
  | "processing"
  | "retrying"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobEvent {
  stage: string;
  at: string;
  message?: string;
}

export interface OutputItem {
  id: string;
  job_id: string;
  url: string;
  mime_type: string;
  size_bytes: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface GalleryItem extends OutputItem {
  prompt: string;
  provider: string | null;
  model: string | null;
  account_label: string | null;
}

export interface Job {
  id: string;
  type: string;
  prompt: string;
  requested_provider: string;
  requested_model: string;
  provider_used: string | null;
  model_used: string | null;
  account_label: string | null;
  number_of_outputs: number;
  status: JobStatus;
  attempts: number;
  error: string | null;
  events: JobEvent[];
  next_retry_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  outputs: OutputItem[];
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface JobCreateInput {
  type: "image_generation";
  prompt: string;
  number_of_outputs: number;
  provider: string;
  model: string;
  size?: string | null;
  quality?: string | null;
}

export interface AccountUsage {
  account_id: string;
  label: string;
  provider: string;
  provider_name: string;
  requests: number;
  images: number;
  input_tokens: number | null;
  output_tokens: number | null;
  last_request_at: string | null;
  provider_usage: { available: boolean; message: string | null; data: Record<string, unknown> };
  rate_limits: RateLimits | null;
  rate_limits_updated_at: string | null;
}

export interface UsageSummary {
  requests: number;
  images: number;
  input_tokens: number | null;
  output_tokens: number | null;
  accounts: AccountUsage[];
  daily: { date: string; requests: number; images: number }[];
}

export interface AuditEntry {
  id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  ip_address: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}
