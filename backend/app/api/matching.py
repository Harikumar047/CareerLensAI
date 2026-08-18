"""
Matching API router.

POST /api/matching/analyze        – single job match
POST /api/matching/analyze-search – match all jobs in a cached search
"""
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.resume import CandidateProfile
from app.models.job import Job
from app.models.matching import (
    JobMatchResult,
    SearchMatchSummary,
    WhatIfRequest,
    WhatIfResponse,
)
from app.services.job_parser import JobParserService
from app.services.matcher import compute_match
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/matching", tags=["matching"])

job_parser = JobParserService()
embedding_svc = EmbeddingService()


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    resume_id: str
    job_id: str


class AnalyzeSearchRequest(BaseModel):
    resume_id: str
    search_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_profile(resume_id: str) -> CandidateProfile:
    path = settings.RESUMES_DIR / f"{resume_id}.json"
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Resume '{resume_id}' not found.")
    try:
        return CandidateProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"Failed to parse stored resume profile: {e}")


def _load_search(search_id: str) -> dict:
    path = settings.JOBS_DIR / f"search_{search_id}.json"
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Search '{search_id}' not found.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            f"Failed to read cached search: {e}")


def _find_job(job_id: str) -> Job:
    """Locate a job by ID within any cached search file."""
    for search_file in settings.JOBS_DIR.glob("search_*.json"):
        try:
            data = json.loads(search_file.read_text(encoding="utf-8"))
            for j in data.get("jobs", []):
                if j.get("id") == job_id:
                    return _job_from_dict(j)
        except Exception:
            continue
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Job '{job_id}' not found in any cached search.",
    )


def _persist_match(data: dict) -> Path:
    match_id = str(uuid.uuid4())
    path = settings.JOBS_DIR / f"matches_{match_id}.json"
    data["match_id"] = match_id
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    data["model_version"] = "NuExtract-tiny-Resume-Data-Extractor + all-MiniLM-L6-v2"
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to persist match result: {e}")
    return path


def _job_from_dict(d: dict) -> Job:
    return Job(**d)


# ---------------------------------------------------------------------------
# POST /api/matching/analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=JobMatchResult, status_code=status.HTTP_200_OK)
async def analyze_single(body: AnalyzeRequest) -> JobMatchResult:
    """
    Match a stored candidate profile against a single job by job_id.
    The job must exist inside one of the cached search files.
    """
    candidate = _load_profile(body.resume_id)
    job = _find_job(body.job_id)

    requirements = job_parser.parse_job_requirements(job)

    result = compute_match(candidate, job, requirements, embedding_svc)

    _persist_match({
        "resume_id": body.resume_id,
        "job_id": body.job_id,
        "result": result.model_dump(),
    })

    return result


# ---------------------------------------------------------------------------
# POST /api/matching/analyze-search
# ---------------------------------------------------------------------------

@router.post("/analyze-search", response_model=SearchMatchSummary, status_code=status.HTTP_200_OK)
async def analyze_search(body: AnalyzeSearchRequest) -> SearchMatchSummary:
    """
    Match a candidate against every job in a cached search result.
    Returns ranked results (eligible first, then by fit_score descending).
    """
    candidate = _load_profile(body.resume_id)
    search_data = _load_search(body.search_id)

    raw_jobs = search_data.get("jobs", [])
    if not raw_jobs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "The cached search contains no jobs.")

    results: list[JobMatchResult] = []
    for j in raw_jobs:
        try:
            job = _job_from_dict(j)
            requirements = job_parser.parse_job_requirements(job)
            match = compute_match(candidate, job, requirements, embedding_svc)
            results.append(match)
        except Exception as e:
            logger.warning(f"Skipping job {j.get('id')} due to error: {e}")
            continue

    # Sort: eligible first, then by fit_score descending
    results.sort(key=lambda r: (not r.eligible, -r.fit_score))

    eligible_count = sum(1 for r in results if r.eligible)
    strong_count = sum(1 for r in results if r.eligible and r.fit_score >= 75)

    match_id = str(uuid.uuid4())
    summary = SearchMatchSummary(
        resume_id=body.resume_id,
        search_id=body.search_id,
        total_jobs=len(results),
        eligible_jobs=eligible_count,
        strong_matches=strong_count,
        matches=results,
        match_id=match_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Persist
    persist_data = summary.model_dump()
    persist_data["model_version"] = "NuExtract-tiny-Resume-Data-Extractor + all-MiniLM-L6-v2"
    path = settings.JOBS_DIR / f"matches_{match_id}.json"
    try:
        path.write_text(json.dumps(persist_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to persist search match: {e}")

    return summary


# ---------------------------------------------------------------------------
# POST /api/matching/what-if
# ---------------------------------------------------------------------------

@router.post("/what-if", response_model=WhatIfResponse, status_code=status.HTTP_200_OK)
async def simulate_what_if(body: WhatIfRequest) -> WhatIfResponse:
    """
    Simulates the impact of acquiring one or more new skills on the Job Fit Score
    for a specific job. Reuses the exact core matching formula.
    Never modifies the candidate's stored resume profile.
    """
    # 1. Load real candidate profile & job
    candidate = _load_profile(body.resume_id)
    job = _find_job(body.job_id)

    # 2. Parse job requirements
    requirements = job_parser.parse_job_requirements(job)

    # 3. Calculate baseline current score using existing matcher
    current_match = compute_match(candidate, job, requirements, embedding_svc)
    current_score = current_match.fit_score

    # 4. Create an isolated copy of candidate and apply skills
    simulated_candidate = candidate.model_copy(deep=True)
    existing_skills = list(simulated_candidate.skills)
    for s in body.skills_to_add:
        clean_s = s.strip()
        if clean_s and clean_s not in existing_skills:
            existing_skills.append(clean_s)
    simulated_candidate.skills = existing_skills

    # 5. Run the existing matcher on simulated candidate
    simulated_match = compute_match(simulated_candidate, job, requirements, embedding_svc)
    simulated_score = simulated_match.fit_score
    improvement = round(simulated_score - current_score, 2)

    # 6. Determine newly matched skills & remaining gaps
    current_missing = set(current_match.missing_required_skills + current_match.missing_preferred_skills)
    simulated_missing = set(simulated_match.missing_required_skills + simulated_match.missing_preferred_skills)

    newly_matched = [s for s in current_missing if s not in simulated_missing]
    remaining_gaps = simulated_match.missing_required_skills + simulated_match.missing_preferred_skills

    # 7. Generate concise explanation
    if improvement > 0:
        added_desc = ", ".join(newly_matched or body.skills_to_add)
        explanation = f"Adding {added_desc} increases alignment with this job."
    elif not body.skills_to_add:
        explanation = "No skills were specified to simulate."
    else:
        explanation = f"Adding {', '.join(body.skills_to_add)} does not change the fit score for this job (already possessed or not required)."

    return WhatIfResponse(
        job_id=body.job_id,
        current_score=current_score,
        simulated_score=simulated_score,
        improvement=improvement,
        skills_added=body.skills_to_add,
        newly_matched_skills=newly_matched,
        remaining_gaps=remaining_gaps,
        explanation=explanation,
    )

