"""
Learning Resource Provider Abstraction.

Allows pluggable dynamic providers (e.g. YouTube Data API, future Coursera/AWS/Microsoft Learn APIs)
alongside verified catalogue fallback.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.models.course import CourseRecommendationItem
from app.services.youtube_service import YouTubeService


class LearningResourceProvider(ABC):
    """Abstract base class for learning resource providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier."""
        pass

    @abstractmethod
    def search(
        self,
        skill: str,
        context: Optional[str] = None,
        max_results: int = 5,
        free_only: bool = False,
        priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        """Search learning resources dynamically for a given skill and context."""
        pass


class YouTubeResourceProvider(LearningResourceProvider):
    """Dynamic YouTube Data API learning resource provider."""

    def __init__(self, youtube_service: Optional[YouTubeService] = None) -> None:
        self.service = youtube_service or YouTubeService()

    @property
    def name(self) -> str:
        return "youtube"

    def search(
        self,
        skill: str,
        context: Optional[str] = None,
        max_results: int = 5,
        free_only: bool = False,
        priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        return self.service.search_learning_resources(
            skill=skill,
            context=context,
            max_results=max_results,
            priority=priority,
        )
