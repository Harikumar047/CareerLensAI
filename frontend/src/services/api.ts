/**
 * Centralized API client for CareerLensAI Backend
 */
import {
  UploadResumeResponse,
  CandidateProfile,
  JobSearchResponse,
  SearchMatchSummary,
  JobMatchResult,
  SkillGapResponse,
  WhatIfRequest,
  WhatIfResponse,
  LearningResourceResponse,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function handleResponse<T>(res: Response, fallbackError: string): Promise<T> {
  if (!res.ok) {
    let errorDetail = fallbackError;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' 
          ? errJson.detail 
          : JSON.stringify(errJson.detail);
      }
    } catch {
      errorDetail = `${fallbackError} (HTTP ${res.status})`;
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /**
   * Health Check
   */
  async checkHealth(): Promise<{ status: string; app_name: string }> {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res, 'Backend service is unreachable');
  },

  /**
   * Page 1: Upload PDF Resume
   */
  async uploadResume(file: File): Promise<UploadResumeResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/api/resume/upload`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res, 'Failed to parse resume PDF');
  },

  /**
   * Page 2: Get Stored Profile
   */
  async getProfile(resumeId: string): Promise<CandidateProfile> {
    const res = await fetch(`${API_BASE}/api/resume/${resumeId}`);
    return handleResponse(res, 'Could not retrieve candidate profile');
  },

  /**
   * Page 3: Live Job Search (Adzuna)
   */
  async searchJobs(role: string, location: string, page = 1): Promise<JobSearchResponse> {
    const params = new URLSearchParams({
      role: role.trim(),
      location: location.trim(),
      page: page.toString(),
      results_per_page: '15',
    });

    const res = await fetch(`${API_BASE}/api/jobs/search?${params.toString()}`);
    return handleResponse(res, 'Failed to fetch live jobs from provider');
  },

  /**
   * Page 4: Analyze Match against search results
   */
  async analyzeSearch(resumeId: string, searchId: string): Promise<SearchMatchSummary> {
    const res = await fetch(`${API_BASE}/api/matching/analyze-search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_id: resumeId, search_id: searchId }),
    });
    return handleResponse(res, 'Failed to calculate job matches');
  },

  /**
   * Single Job Match Analysis
   */
  async analyzeSingleJob(resumeId: string, jobId: string): Promise<JobMatchResult> {
    const res = await fetch(`${API_BASE}/api/matching/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_id: resumeId, job_id: jobId }),
    });
    return handleResponse(res, 'Failed to match job');
  },

  /**
   * Page 5: Skill Gap Analysis
   */
  async getSkillGaps(resumeId: string, searchId: string): Promise<SkillGapResponse> {
    const res = await fetch(`${API_BASE}/api/skills/gaps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resume_id: resumeId, search_id: searchId }),
    });
    return handleResponse(res, 'Failed to analyze skill gaps');
  },

  /**
   * Page 6: What-If Skill Simulator
   */
  async simulateWhatIf(payload: WhatIfRequest): Promise<WhatIfResponse> {
    const res = await fetch(`${API_BASE}/api/matching/what-if`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res, 'Skill simulation failed');
  },

  /**
   * Page 7: Dynamic Learning Resource Recommendations
   */
  async getCourseRecommendations(
    resumeId?: string,
    searchId?: string,
    skills?: string[],
    freeOnly = false,
    maxPerSkill = 3
  ): Promise<LearningResourceResponse> {
    const payload: {
      resume_id?: string;
      search_id?: string;
      skills?: string[];
      free_only: boolean;
      max_per_skill: number;
    } = {
      free_only: freeOnly,
      max_per_skill: maxPerSkill,
    };

    if (resumeId && searchId) {
      payload.resume_id = resumeId;
      payload.search_id = searchId;
    } else if (skills && skills.length > 0) {
      payload.skills = skills;
    }

    const res = await fetch(`${API_BASE}/api/courses/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res, 'Failed to discover learning resources');
  },
};
