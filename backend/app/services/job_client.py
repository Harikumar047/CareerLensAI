import httpx
import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from app.config import settings
from app.models.job import Job

logger = logging.getLogger(__name__)

class AdzunaJobClient:
    """
    Client for retrieving and normalizing jobs from the Adzuna API.
    """

    def __init__(self) -> None:
        self.country = settings.ADZUNA_COUNTRY or "in"
        self.base_url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search"

    def _verify_credentials(self, app_id: Optional[str], app_key: Optional[str]) -> None:
        """
        Ensures Adzuna API credentials are configured.
        """
        if not app_id or not app_key:
            logger.error("Adzuna credentials are missing. ADZUNA_APP_ID or ADZUNA_APP_KEY not set.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Job search service is misconfigured. Please check environment configuration."
            )

    def normalize_job(self, raw_job: Dict[str, Any]) -> Job:
        """
        Maps the raw Adzuna response object fields to our normalized Job schema.
        """
        job_id = raw_job.get("id")
        formatted_id = f"adzuna_{job_id}" if job_id else ""

        company_info = raw_job.get("company", {})
        company_name = company_info.get("display_name") if isinstance(company_info, dict) else None

        location_info = raw_job.get("location", {})
        location_name = location_info.get("display_name") if isinstance(location_info, dict) else None

        category_info = raw_job.get("category", {})
        category_label = category_info.get("label") if isinstance(category_info, dict) else None

        return Job(
            id=formatted_id,
            source="adzuna",
            title=raw_job.get("title", "Untitled Job"),
            company=company_name,
            location=location_name,
            description=raw_job.get("description"),
            salary_min=raw_job.get("salary_min"),
            salary_max=raw_job.get("salary_max"),
            contract_type=raw_job.get("contract_type"),
            contract_time=raw_job.get("contract_time"),
            category=category_label,
            created=raw_job.get("created"),
            url=raw_job.get("redirect_url")
        )

    async def search_jobs(
        self,
        role: str,
        location: str,
        page: int = 1,
        results_per_page: int = 20,
        max_days_old: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Queries the Adzuna API for jobs matching search criteria and normalizes results.
        """
        app_id = settings.ADZUNA_APP_ID
        app_key = settings.ADZUNA_APP_KEY

        self._verify_credentials(app_id, app_key)

        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": role,
            "where": location,
            "results_per_page": results_per_page,
            "content-type": "application/json"
        }

        if max_days_old is not None:
            params["max_days_old"] = max_days_old

        url = f"{self.base_url}/{page}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                
                # Check for rate limiting
                if response.status_code == 429:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded for the job search provider. Please try again later."
                    )
                
                # Check for unauthorized credentials
                if response.status_code in (401, 403):
                    logger.error(f"Adzuna authentication failed (HTTP {response.status_code}). check keys.")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Authentication failed with the job search provider. Configuration issue."
                    )

                # Raise for other HTTP errors
                response.raise_for_status()
                
                data = response.json()
        except httpx.TimeoutException:
            logger.error("Timeout occurred while connecting to Adzuna API.")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Request to the job search provider timed out."
            )
        except httpx.RequestError as re:
            logger.error(f"Request connection error to Adzuna API: {str(re)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to establish connection with the job search provider."
            )
        except (ValueError, KeyError, TypeError) as pe:
            logger.error(f"Malformed response from Adzuna API: {str(pe)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Job search provider returned an invalid or malformed response."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying jobs: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during job retrieval: {str(e)}"
            )

        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            logger.error("Adzuna 'results' field is not a list.")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Job search provider returned malformed search results."
            )

        # Normalize results
        normalized_jobs = []
        for raw_job in raw_results:
            try:
                normalized_jobs.append(self.normalize_job(raw_job))
            except Exception as ne:
                logger.warning(f"Skipping normalization of single job entry due to error: {ne}")
                continue

        # total count of matches
        total_count = data.get("count", len(normalized_jobs))

        return {
            "total_returned": len(normalized_jobs),
            "total_count": total_count,
            "jobs": normalized_jobs
        }
