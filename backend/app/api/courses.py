"""
Course & Learning Resource API Router.

Endpoints:
- POST /api/courses/recommendations - Recommend real resources for student skill gaps
- GET  /api/courses/recommendations - Query-based resource recommendations
- GET  /api/courses                 - List all verified learning resources
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.models.course import (
    Course,
    CourseRecommendationItem,
    CourseRecommendationResponse,
    CourseRecommendationRequest,
)
from app.models.job import Job
from app.models.job_requirements import JobRequirements
from app.models.resume import CandidateProfile
from app.services.course_recommender import CourseRecommenderService
from app.services.job_parser import JobParserService
from app.services.skill_gap_analyzer import analyze_skill_gaps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/courses", tags=["courses"])

recommender_service = CourseRecommenderService()
job_parser = JobParserService()


def _load_profile(resume_id: str) -> CandidateProfile:
    """Loads a candidate profile from the data/resumes directory."""
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
    """Loads cached job search results from the data/jobs directory."""
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


def _get_recommendations_for_search(
    resume_id: str,
    search_id: str,
    free_only: bool = False,
    max_per_skill: int = 3,
) -> List[CourseRecommendationItem]:
    """Helper to extract skill gaps and recommend real resources for a candidate against a job search."""
    candidate = _load_profile(resume_id)
    search_data = _load_search(search_id)

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

    # Analyze missing skills
    skill_gaps = analyze_skill_gaps(candidate, requirements_list)

    # Recommend verified resources for HIGH & MEDIUM priority gaps
    return recommender_service.recommend_for_skill_gaps(
        skill_gaps=skill_gaps,
        requirements_list=requirements_list,
        free_only=free_only,
        max_per_skill=max_per_skill,
    )


@router.get("", response_model=List[Course], status_code=status.HTTP_200_OK)
async def list_courses(
    skill: Optional[str] = Query(None, description="Filter courses by specific skill"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type ('youtube' or 'coursera')"),
    free_only: bool = Query(False, description="Filter only free courses"),
) -> List[Course]:
    """
    Retrieve verified learning resources in the catalogue.
    """
    if skill:
        return recommender_service.find_courses_for_skill(
            skill, free_only=free_only, resource_type=resource_type
        )
    courses = recommender_service.get_all_courses()
    if resource_type:
        courses = [c for c in courses if c.resource_type.lower() == resource_type.lower()]
    if free_only:
        courses = [c for c in courses if c.free]
    return courses


@router.post(
    "/recommendations",
    response_model=CourseRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def recommend_courses_post(
    body: CourseRecommendationRequest,
) -> CourseRecommendationResponse:
    """
    Recommend real, clickable learning resources for a student's missing skills.

    Accepts:
    - `resume_id` + `search_id`: Automatically identifies skill gaps from resume vs target jobs.
    - `skills`: Direct list of target skills.
    """
    if body.resume_id and body.search_id:
        items = _get_recommendations_for_search(
            resume_id=body.resume_id,
            search_id=body.search_id,
            free_only=body.free_only,
            max_per_skill=body.max_per_skill,
        )
        return CourseRecommendationResponse(recommendations=items)

    if body.skills:
        items = recommender_service.recommend_for_skills(
            skills=body.skills,
            free_only=body.free_only,
            max_per_skill=body.max_per_skill,
        )
        return CourseRecommendationResponse(recommendations=items)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either (resume_id and search_id) or a non-empty skills list must be provided.",
    )


@router.get(
    "/recommendations",
    response_model=CourseRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
async def recommend_courses_get(
    resume_id: Optional[str] = Query(None, description="UUID of parsed resume"),
    search_id: Optional[str] = Query(None, description="UUID of cached job search"),
    skills: Optional[List[str]] = Query(None, description="List of target skill names"),
    free_only: bool = Query(False, description="Filter only free courses"),
    max_per_skill: int = Query(3, ge=1, le=10, description="Max courses per skill"),
) -> CourseRecommendationResponse:
    """
    GET endpoint to recommend learning resources via query parameters.
    """
    if resume_id and search_id:
        items = _get_recommendations_for_search(
            resume_id=resume_id,
            search_id=search_id,
            free_only=free_only,
            max_per_skill=max_per_skill,
        )
        return CourseRecommendationResponse(recommendations=items)

    if skills:
        items = recommender_service.recommend_for_skills(
            skills=skills,
            free_only=free_only,
            max_per_skill=max_per_skill,
        )
        return CourseRecommendationResponse(recommendations=items)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either (resume_id and search_id) or a non-empty skills list must be provided.",
    )
