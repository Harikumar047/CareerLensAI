from pydantic import BaseModel, Field
from typing import List, Optional


class EligibilityResult(BaseModel):
    """Result of checking a candidate against hard job requirements."""
    eligible: bool
    reasons: List[str] = Field(default_factory=list)
    hard_failures: List[str] = Field(default_factory=list)


class SkillMatchResult(BaseModel):
    """Result of comparing candidate skills against job requirements."""
    matched_required_skills: List[str] = Field(default_factory=list)
    missing_required_skills: List[str] = Field(default_factory=list)
    matched_preferred_skills: List[str] = Field(default_factory=list)
    missing_preferred_skills: List[str] = Field(default_factory=list)
    required_skill_score: float = 0.0
    preferred_skill_score: float = 0.0


class JobMatchResult(BaseModel):
    """Full match analysis result for a single job."""
    job_id: str
    eligible: bool
    fit_score: float = Field(..., description=(
        "Job Fit Score (0–100) representing alignment between the candidate's "
        "demonstrated profile and the requirements in this job description. "
        "It does not guarantee recruiter shortlisting."
    ))
    required_skill_score: float = 0.0
    preferred_skill_score: float = 0.0
    project_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    semantic_score: float = 0.0
    matched_skills: List[str] = Field(default_factory=list)
    missing_required_skills: List[str] = Field(default_factory=list)
    missing_preferred_skills: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    recommendation: str = ""
    eligibility_reasons: List[str] = Field(default_factory=list)
    hard_failures: List[str] = Field(default_factory=list)


class SearchMatchSummary(BaseModel):
    """Summary of matching a candidate against an entire job search result set."""
    resume_id: str
    search_id: str
    total_jobs: int
    eligible_jobs: int
    strong_matches: int
    matches: List[JobMatchResult]
    match_id: str
    timestamp: str


class WhatIfRequest(BaseModel):
    """Request to simulate the impact of adding skills to a candidate's profile."""
    resume_id: str = Field(..., description="UUID of candidate's parsed resume")
    job_id: str = Field(..., description="Target job ID from search results")
    skills_to_add: List[str] = Field(default_factory=list, description="List of skills to simulate adding")


class WhatIfResponse(BaseModel):
    """Response showing score improvement and impact of simulated skill additions."""
    job_id: str = Field(..., description="Target job ID")
    current_score: float = Field(..., description="Current Job Fit Score (0-100)")
    simulated_score: float = Field(..., description="Simulated Job Fit Score (0-100) after adding skills")
    improvement: float = Field(..., description="Score increase in points")
    skills_added: List[str] = Field(default_factory=list, description="Skills submitted for simulation")
    newly_matched_skills: List[str] = Field(default_factory=list, description="Skills that successfully fulfilled job requirements")
    remaining_gaps: List[str] = Field(default_factory=list, description="Skills still missing for this job")
    explanation: str = Field(..., description="Human-readable explanation of alignment changes")

