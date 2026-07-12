/** DTOs mirroring the FastAPI schemas (backend/app/schemas). */

export type UserRole = 'admin' | 'user';
export type MatchBand = 'high' | 'medium_high' | 'stretch';
export type EligibilityStatus = 'actionable' | 'eligibility_gated';
export type SearchMode = 'daily' | 'catchup';
export type LlmProvider = 'anthropic' | 'openai';
export type ResumeFormat = 'pdf' | 'docx' | 'latex';
export type ProviderSlug =
  | 'adzuna'
  | 'jooble'
  | 'jsearch'
  | 'remotive'
  | 'greenhouse_lever'
  | 'serpapi_google_jobs'
  | 'apify_linkedin'
  | 'apify_naukri';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface ProfileSkill {
  id: number;
  name: string;
  weight: number;
  is_required: boolean;
  proficiency: string | null;
}

export interface Profile {
  id: number;
  name: string;
  headline: string | null;
  is_default: boolean;
  experience_min_years: number;
  experience_max_years: number | null;
  target_roles: string[];
  preferred_companies: string[];
  ignored_companies: string[];
  certifications: string[];
  languages: string[];
  locations: string[];
  work_modes: string[];
  scoring_weights: Record<string, number>;
  min_score: number;
  company_size_mode: boolean;
  max_headcount: number | null;
  skills: ProfileSkill[];
  created_at: string;
}

export interface MatchJob {
  id: number;
  title: string;
  company: string;
  location: string | null;
  url: string;
  apply_url: string | null;
  is_remote: boolean;
  salary_raw: string | null;
  company_headcount: number | null;
}

export interface Match {
  id: number;
  profile_id: number;
  score: number;
  band: MatchBand;
  eligibility_status: EligibilityStatus;
  component_scores: Record<string, number>;
  strengths: string[];
  missing_skills: string[];
  explanation: string | null;
  recommendation: string | null;
  notified: boolean;
  created_at: string;
  job: MatchJob;
}

export interface Provider {
  id: number;
  slug: ProviderSlug;
  display_name: string;
  requires_credentials: string[];
  is_apify: boolean;
  is_active: boolean;
  last_health_status: 'unknown' | 'healthy' | 'unhealthy';
  last_checked_at: string | null;
}

export interface AppSettings {
  llm_provider: LlmProvider | null;
  llm_model: string | null;
  telegram_enabled: boolean;
  telegram_chat_id: string | null;
  email_enabled: boolean;
  notify_email: string | null;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  notify_cap: number;
  locale: string;
  theme: string;
}

export interface Credential {
  key: string;
  masked_value: string;
  updated_at: string;
}

export interface SavedSearch {
  id: number;
  profile_id: number;
  name: string;
  provider_slug: ProviderSlug | null;
  mode: SearchMode;
  is_active: boolean;
  params: Record<string, unknown>;
  last_run_at: string | null;
  created_at: string;
}

export interface Resume {
  id: number;
  profile_id: number;
  filename: string;
  format: ResumeFormat;
  parse_status: 'pending' | 'parsed' | 'failed';
  parse_error: string | null;
  is_primary: boolean;
  created_at: string;
}

export interface IngestionResult {
  profile_id: number;
  searches_run: number;
  candidates: number;
  new_jobs: number;
  providers: { provider: ProviderSlug; fetched: number; healthy: boolean; error: string | null }[];
}

export interface MatchingResult {
  profile_id: number;
  evaluated: number;
  qualified: number;
  below_gate: number;
  excluded_by_company_size: number;
  eligibility_gated: number;
  explanations_generated: number;
  llm_enabled: boolean;
}

export interface NotificationResult {
  profile_id: number;
  selected: number;
  channels: { channel: 'telegram' | 'email'; sent: boolean; error: string | null }[];
  notified_match_ids: number[];
}

export interface PipelineResult {
  profile_id: number;
  mode: SearchMode;
  ingestion: IngestionResult;
  matching: MatchingResult;
  notification: NotificationResult;
}
