"""
Course & Learning Resource models for CareerLensAI Course Recommendation system.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Course(BaseModel):
    """
    Represents a verified educational course or learning resource in the catalogue.
    """
    id: str = Field(..., description="Unique identifier for the course/resource")
    skill: str = Field(..., description="Target skill covered by the resource")
    title: str = Field(..., description="Course or video title")
    provider: str = Field(..., description="Platform or Channel (e.g. YouTube, Coursera, freeCodeCamp)")
    resource_type: Literal["youtube", "coursera"] = Field(
        ..., description="Type of resource: 'youtube' or 'coursera'"
    )
    level: Literal["beginner", "intermediate", "advanced"] = Field(
        ..., description="Difficulty level"
    )
    free: bool = Field(..., description="Whether the resource is free to access")
    url: str = Field(..., description="Real, verified clickable URL")
    description: str = Field(..., description="Short summary of what is taught")
    thumbnail: Optional[str] = Field(None, description="Image thumbnail URL if available")
    published_at: Optional[str] = Field(None, description="Publish date/time if available")


class CourseRecommendationItem(BaseModel):
    """
    Represents a recommended resource for an identified skill gap.
    """
    skill: str = Field(..., description="Missing skill name")
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Priority level of the skill gap"
    )
    title: str = Field(..., description="Resource title")
    provider: str = Field(..., description="Platform or Channel")
    resource_type: Literal["youtube", "coursera"] = Field(
        ..., description="Type of resource ('youtube' or 'coursera')"
    )
    level: Literal["beginner", "intermediate", "advanced"] = Field(
        ..., description="Difficulty level"
    )
    free: bool = Field(..., description="Whether the resource is free")
    url: str = Field(..., description="Real, clickable URL")
    description: str = Field(..., description="Short description of the course")
    thumbnail: Optional[str] = Field(None, description="Image thumbnail URL if available")
    published_at: Optional[str] = Field(None, description="Publish date/time if available")


class CourseRecommendationResponse(BaseModel):
    """
    Response model containing recommended resources for the student's highest priority skill gaps.
    """
    recommendations: List[CourseRecommendationItem] = Field(
        default_factory=list, description="Ranked list of real learning resources"
    )


class CourseRecommendationRequest(BaseModel):
    """
    Request payload for recommending courses based on resume & job search or direct skills.
    """
    resume_id: Optional[str] = Field(None, description="UUID of candidate's parsed resume")
    search_id: Optional[str] = Field(None, description="UUID of cached job search")
    skills: Optional[List[str]] = Field(None, description="Optional explicit list of skills")
    free_only: bool = Field(False, description="If True, only return free learning resources")
    max_per_skill: int = Field(3, ge=1, le=10, description="Max resources to recommend per missing skill")
