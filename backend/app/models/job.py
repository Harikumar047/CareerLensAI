from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Job(BaseModel):
    id: str = Field(..., description="Unique job identifier")
    source: str = Field("adzuna", description="Source of the job listing")
    title: str = Field(..., description="Job title")
    company: Optional[str] = Field(None, description="Company name")
    location: Optional[str] = Field(None, description="Job location")
    description: Optional[str] = Field(None, description="Job description snippet")
    salary_min: Optional[float] = Field(None, description="Minimum salary")
    salary_max: Optional[float] = Field(None, description="Maximum salary")
    contract_type: Optional[str] = Field(None, description="Contract type (e.g. permanent, contract)")
    contract_time: Optional[str] = Field(None, description="Contract time (e.g. full_time, part_time)")
    category: Optional[str] = Field(None, description="Job category classification")
    created: Optional[str] = Field(None, description="Creation date ISO string")
    url: Optional[str] = Field(None, description="Original job post URL")

class QueryInfo(BaseModel):
    role: str
    location: str
    page: int = 1
    results_per_page: int = 20
    max_days_old: Optional[int] = None

class JobSearchResponse(BaseModel):
    query: QueryInfo
    total_returned: int
    jobs: List[Job]
    retrieved_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO timestamp indicating when the search was fetched"
    )
