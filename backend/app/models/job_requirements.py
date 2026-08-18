from pydantic import BaseModel, Field
from typing import List, Optional


class JobRequirements(BaseModel):
    """Extracted structured requirements from a job description."""
    job_id: str
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    education_requirements: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    employment_type: Optional[str] = None
    extracted_keywords: List[str] = Field(default_factory=list)
