export type Fact = {
  field: string;
  value: string;
  source: "cv" | "context" | "inference" | "user";
  evidence: string;
  verified: boolean;
};

export type CandidateProfile = {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  title: string;
  skills: string[];
  experience_years: number | null;
  seniority: string | null;
  languages: Record<string, string>;
  education: string[];
  certifications: string[];
  projects: string[];
  summary: string;
  facts: Fact[];
  reviewed: boolean;
  [key: string]: unknown;
};

export type ProfileRecord = {
  id: string;
  version: number;
  profile: CandidateProfile;
  reviewed: boolean;
};

export type ContextBundle = {
  candidate_context: string;
  custom_instructions: string;
  preferences: Record<string, unknown>;
  rules: {
    minimum_score: number;
    max_daily: number;
    max_weekly: number;
    permitted_sources: string[];
    mode: "manual" | "semi_automatic" | "automatic";
    requires_approval: boolean;
    automatic_enabled: boolean;
    third_party_consent: boolean;
    llm_consent: boolean;
    max_retries: number;
    search_interval_hours: number;
    matching_weights: Record<string, number>;
    [key: string]: unknown;
  };
  version?: number;
};

export type Match = {
  score: number;
  eligible: boolean;
  decision: string;
  matches: string[];
  gaps: string[];
  blockers: string[];
  breakdown: Record<string, number>;
  requires_human_review?: boolean;
};

export type Job = {
  id: string;
  source: string;
  external_id: string;
  title: string;
  company: string;
  url: string;
  description: string;
  location: string;
  work_mode: string;
  skills: string[];
  minimum_years: number | null;
  seniority: string | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  salary_period: string | null;
  languages: Record<string, string>;
  mandatory_requirements: string[];
  published_at: string | null;
  contract_type: string | null;
  match: Match | null;
  ingestion_method?: "api" | "assisted";
  application_state?: string | null;
};

export type Application = {
  id: string;
  job_id: string;
  job_title: string;
  company: string;
  source: string;
  url: string;
  state: string;
  packet: {
    summary?: string;
    cover_letter?: string;
    cv_text?: string;
    selected_projects?: string[];
    questions?: Record<string, unknown> | unknown[];
    pending_questions?: unknown[];
    [key: string]: unknown;
  };
  approved: boolean;
  created_at: string;
  updated_at: string;
  result_reference: string | null;
  events?: { kind: string; message: string; created_at: string }[];
};

export type Dashboard = {
  jobs: number;
  eligible_jobs: number;
  applications: number;
  pending_approval: number;
  submitted: number;
  confirmed: number;
  real_submitted: number;
  demo_submitted: number;
  platform_confirmed: number;
  user_confirmed: number;
  average_score: number;
  ai_cost_usd: number | null;
  ai_cost_note?: string;
  automation_enabled: boolean;
  recent_events: {
    id: string;
    kind: string;
    message: string;
    created_at: string;
  }[];
  skill_gaps: { skill: string; count: number }[];
};

export type Source = {
  name: string;
  label: string;
  capabilities: Record<string, boolean> | string[];
  description: string;
};

export type Task = {
  id: string;
  status: string;
  result: unknown;
  error: string | null;
};
