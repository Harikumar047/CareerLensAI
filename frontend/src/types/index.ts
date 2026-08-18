// API & Data Types for CareerLensAI

export interface Education {
  degree?: string | null;
  institution?: string | null;
  graduation_year?: number | null;
  field_of_study?: string | null;
}

export interface Experience {
  company?: string | null;
  role?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
  skills?: string[] | null;
}

export interface Project {
  name?: string | null;
  description?: string | null;
  technologies?: string[] | null;
  url?: string | null;
}

export interface CandidateProfile {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  skills: string[];
  education: Education[];
  experience: Experience[];
  projects: Project[];
  certifications?: string[];
  total_experience_years?: number | null;
  preferred_roles?: string[];
}

export interface UploadResumeResponse {
  resume_id: string;
  profile: CandidateProfile;
  extraction_summary: {
    skills_found: number;
    projects_found: number;
    experience_entries: number;
    education_entries: number;
  };
}

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string;
  location: string;
  description: string;
  salary_min?: number | null;
  salary_max?: number | null;
  contract_type?: string | null;
  contract_time?: string | null;
  category?: string | null;
  created?: string | null;
  url: string;
}

export interface JobSearchResponse {
  query: {
    role: string;
    location: string;
    page: number;
    results_per_page: number;
  };
  total_returned: number;
  jobs: Job[];
  retrieved_at: string;
  search_id?: string;
}

export interface JobMatchResult {
  job_id: string;
  eligible: boolean;
  fit_score: number;
  required_skill_score: number;
  preferred_skill_score: number;
  project_score: number;
  experience_score: number;
  education_score: number;
  semantic_score: number;
  matched_skills: string[];
  missing_required_skills: string[];
  missing_preferred_skills: string[];
  strengths: string[];
  gaps: string[];
  recommendation: string;
  eligibility_reasons: string[];
  hard_failures: string[];
}

export interface SearchMatchSummary {
  resume_id: string;
  search_id: string;
  total_jobs: number;
  eligible_jobs: number;
  strong_matches: number;
  matches: JobMatchResult[];
  match_id: string;
  timestamp: string;
}

export interface SkillGapItem {
  skill: string;
  jobs_affected: number;
  percentage: number;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface SkillGapResponse {
  resume_id: string;
  search_id: string;
  total_jobs_analyzed: number;
  skill_gaps: SkillGapItem[];
}

export interface WhatIfRequest {
  resume_id: string;
  job_id: string;
  skills_to_add: string[];
}

export interface WhatIfResponse {
  job_id: string;
  current_score: number;
  simulated_score: number;
  improvement: number;
  skills_added: string[];
  newly_matched_skills: string[];
  remaining_gaps: string[];
  explanation: string;
}

export interface LearningResourceItem {
  skill: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  title: string;
  provider: string;
  resource_type: 'youtube' | 'coursera' | string;
  level: 'beginner' | 'intermediate' | 'advanced' | string;
  free: boolean;
  url: string;
  description: string;
  thumbnail?: string | null;
  published_at?: string | null;
}

export interface LearningResourceResponse {
  recommendations: LearningResourceItem[];
}

export type AppStep =
  | 'upload'
  | 'profile'
  | 'jobs'
  | 'matches'
  | 'gaps'
  | 'what-if'
  | 'learning';
