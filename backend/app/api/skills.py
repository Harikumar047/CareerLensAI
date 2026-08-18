"""
Skills API router.

POST /api/skills/gaps - Analyzes missing skills against a cached job search.
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.models.resume import CandidateProfile
from app.models.job import Job
from app.models.job_requirements import JobRequirements
from app.models.skill_gap import SkillGapResponse
from app.services.job_parser import JobParserService
from app.services.skill_gap_analyzer import analyze_skill_gaps

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/skills", tags=["skills"])

job_parser = JobParserService()


class SkillGapRequest(BaseModel):
    resume_id: str
    search_id: str


def _load_profile(resume_id: str) -> CandidateProfile:
    path = settings.RESUMES_DIR / f"{resume_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume '{resume_id}' not found.",
        )
    try:
        return CandidateProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse stored resume profile: {e}",
        )


def _load_search(search_id: str) -> dict:
    path = settings.JOBS_DIR / f"search_{search_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search '{search_id}' not found.",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read cached search: {e}",
        )


@router.post("/gaps", response_model=SkillGapResponse, status_code=status.HTTP_200_OK)
async def get_skill_gaps(body: SkillGapRequest) -> SkillGapResponse:
    """
    Identifies and ranks missing skills by analyzing the candidate's resume
    against all jobs in a cached job search.
    """
    candidate = _load_profile(body.resume_id)
    search_data = _load_search(body.search_id)

    raw_jobs = search_data.get("jobs", [])
    if not raw_jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The cached search contains no jobs.",
        )

    requirements_list: list[JobRequirements] = []
    for j in raw_jobs:
        try:
            job = Job(**j)
            req = job_parser.parse_job_requirements(job)
            requirements_list.append(req)
        except Exception as e:
            logger.warning(f"Skipping job requirement extraction for job {j.get('id')}: {e}")
            continue

    gaps = analyze_skill_gaps(candidate, requirements_list)

    return SkillGapResponse(
        resume_id=body.resume_id,
        search_id=body.search_id,
        total_jobs_analyzed=len(requirements_list),
        skill_gaps=gaps,
    )
