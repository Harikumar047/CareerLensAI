import uuid
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status
from app.config import settings
from app.models.job import JobSearchResponse, QueryInfo
from app.services.job_client import AdzunaJobClient

router = APIRouter(prefix="/jobs", tags=["jobs"])
job_client = AdzunaJobClient()

@router.get("/search", response_model=JobSearchResponse, status_code=status.HTTP_200_OK)
async def search_jobs(
    role: str = Query(..., description="Job role or search query"),
    location: str = Query(..., description="Location of job search"),
    page: int = Query(1, ge=1, description="Page number of search results"),
    results_per_page: int = Query(20, ge=1, le=50, description="Results to return per page"),
    max_days_old: Optional[int] = Query(None, ge=1, description="Max age of job listings in days")
) -> JobSearchResponse:
    """
    Search jobs live from Adzuna API, normalize results, and cache search footprint locally.
    """
    # 1. Fetch live jobs via AdzunaJobClient
    result = await job_client.search_jobs(
        role=role,
        location=location,
        page=page,
        results_per_page=results_per_page,
        max_days_old=max_days_old
    )

    # 2. Build Response
    query_info = QueryInfo(
        role=role,
        location=location,
        page=page,
        results_per_page=results_per_page,
        max_days_old=max_days_old
    )

    response_data = JobSearchResponse(
        query=query_info,
        total_returned=result["total_returned"],
        jobs=result["jobs"]
    )

    # 3. Store normalized results under app/data/jobs/search_<uuid>.json
    search_id = str(uuid.uuid4())
    save_filename = f"search_{search_id}.json"
    save_path = settings.JOBS_DIR / save_filename

    # Build the record block to store
    storage_record = {
        "search_id": search_id,
        "search_parameters": query_info.model_dump(),
        "timestamp": response_data.retrieved_at,
        "source": "adzuna",
        "jobs": [job.model_dump() for job in response_data.jobs]
    }

    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(storage_record, f, indent=2)
    except Exception as e:
        # We don't crash the request if storage fails, but log it
        import logging
        logging.getLogger("app.api.jobs").error(f"Failed to cache search record: {e}")

    return response_data
