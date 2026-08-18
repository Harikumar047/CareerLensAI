from typing import List, Literal
from pydantic import BaseModel, Field


class SkillGapItem(BaseModel):
    """Represents a single identified missing skill and its impact across jobs."""
    skill: str = Field(..., description="Name of the missing skill")
    jobs_affected: int = Field(..., description="Number of matching jobs requiring or preferring this skill")
    percentage: float = Field(..., description="Percentage of analyzed jobs affected by this missing skill")
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Priority level based on job frequency (HIGH >= 50%, MEDIUM >= 25%, LOW < 25%)"
    )


class SkillGapResponse(BaseModel):
    """Response containing ranked skill gaps for a candidate across a set of jobs."""
    resume_id: str
    search_id: str
    total_jobs_analyzed: int
    skill_gaps: List[SkillGapItem] = Field(default_factory=list)
