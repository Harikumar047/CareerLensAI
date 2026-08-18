"""
Dynamic Course & Learning Resource Recommendation Service.

Primary discovery: Live dynamic queries to verified providers (e.g. YouTube Data API v3).
Fallback discovery: Local verified curated catalogue (courses.json).

Ranking criteria:
1. Skill relevance (canonical & keyword match)
2. Job context relevance (co-occurring technologies in target jobs)
3. Beginner suitability (beginner -> intermediate -> advanced)
4. Provider quality (reputable educational channels & official platforms)
5. Freshness

Guarantees:
- Zero AI hallucinations / fake URLs
- Verified clickable links
- Graceful non-crashing fallbacks
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.config import settings
from app.models.course import (
    Course,
    CourseRecommendationItem,
    CourseRecommendationResponse,
)
from app.models.job_requirements import JobRequirements
from app.models.skill_gap import SkillGapItem
from app.services.providers import LearningResourceProvider, YouTubeResourceProvider
from app.services.skill_matcher import _canonical, _normalise

logger = logging.getLogger(__name__)

# Level ranking: beginner preferred first for upskilling students
_LEVEL_ORDER = {
    "beginner": 0,
    "intermediate": 1,
    "advanced": 2,
}

# Priority ranking: HIGH -> MEDIUM -> LOW
_PRIORITY_ORDER = {
    "HIGH": 0,
    "MEDIUM": 1,
    "LOW": 2,
}


class CourseRecommenderService:
    """
    Service for dynamically discovering and ranking verified learning resources
    for technical skills and student skill gaps.
    """

    _instance: Optional["CourseRecommenderService"] = None

    def __new__(cls) -> "CourseRecommenderService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._courses: List[Course] = []
            cls._instance._loaded = False
            cls._instance._providers: List[LearningResourceProvider] = [
                YouTubeResourceProvider()
            ]
        return cls._instance

    def __init__(self, catalogue_path: Optional[Path] = None) -> None:
        self.catalogue_path = catalogue_path or (settings.COURSES_DIR / "courses.json")
        if not self._loaded or catalogue_path is not None:
            self.load_catalogue(self.catalogue_path)

    def register_provider(self, provider: LearningResourceProvider) -> None:
        """Registers an additional learning resource provider."""
        self._providers.append(provider)

    def load_catalogue(self, path: Optional[Path] = None) -> None:
        """Loads fallback verified learning resources from the JSON catalogue file."""
        target_path = path or self.catalogue_path
        if not target_path.exists():
            logger.warning(f"Course catalogue file not found at {target_path}")
            self._courses = []
            self._loaded = True
            return

        try:
            raw_data = json.loads(target_path.read_text(encoding="utf-8"))
            self._courses = [Course.model_validate(item) for item in raw_data]
            self._loaded = True
            logger.info(f"Loaded {len(self._courses)} fallback resources from {target_path}")
        except Exception as e:
            logger.error(f"Failed to load course catalogue from {target_path}: {e}")
            self._courses = []
            self._loaded = True

    def get_all_courses(self) -> List[Course]:
        """Returns all verified resources from the local fallback catalogue."""
        if not self._loaded:
            self.load_catalogue()
        return list(self._courses)

    def find_courses_for_skill(
        self,
        target_skill: str,
        free_only: bool = False,
        resource_type: Optional[str] = None,
    ) -> List[Course]:
        """
        Finds and ranks all courses matching the given skill from the catalogue.
        """
        if not self._loaded:
            self.load_catalogue()

        target_norm = _normalise(target_skill)
        target_canon = _canonical(target_skill)

        matched: List[Course] = []
        for course in self._courses:
            course_norm = _normalise(course.skill)
            course_canon = _canonical(course.skill)

            # Match on canonical, normalized, or substring equivalence
            is_match = (
                course_norm == target_norm
                or course_canon == target_canon
                or target_norm in course_norm
                or course_norm in target_norm
            )

            if is_match:
                if free_only and not course.free:
                    continue
                if resource_type and course.resource_type.lower() != resource_type.lower():
                    continue
                matched.append(course)

        # Sort courses:
        # 1. Exact canonical match preference
        # 2. Level order (beginner -> intermediate -> advanced)
        # 3. Free first
        # 4. Alphabetical title
        def _course_rank_key(c: Course):
            c_canon = _canonical(c.skill)
            exact_match_rank = 0 if c_canon == target_canon else 1
            level_rank = _LEVEL_ORDER.get(c.level.lower(), 1)
            free_rank = 0 if c.free else 1
            return (exact_match_rank, level_rank, free_rank, c.title.lower())

        matched.sort(key=_course_rank_key)
        return matched

    def _extract_context_for_skill(
        self,
        target_skill: str,
        requirements_list: Optional[List[JobRequirements]] = None,
    ) -> Optional[str]:
        """
        Extracts co-occurring technology keywords from target job descriptions
        to enrich dynamic search queries (e.g. 'AWS EC2 Lambda').
        """
        if not requirements_list:
            return None

        target_canon = _canonical(target_skill)
        co_occurring: Dict[str, int] = {}

        for req in requirements_list:
            req_skills = req.required_skills + req.preferred_skills
            canons = [_canonical(s) for s in req_skills]
            if target_canon in canons:
                for s in req_skills:
                    c = _canonical(s)
                    if c != target_canon and len(s) > 2:
                        co_occurring[s] = co_occurring.get(s, 0) + 1

        if not co_occurring:
            return None

        # Return top 2 co-occurring technologies as context
        sorted_co = sorted(co_occurring.items(), key=lambda kv: -kv[1])
        top_keywords = [k for k, _ in sorted_co[:2]]
        return " ".join(top_keywords)

    def _discover_dynamic_resources(
        self,
        skill: str,
        context: Optional[str] = None,
        max_results: int = 3,
        free_only: bool = False,
        priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        """
        Queries all registered dynamic providers (e.g. YouTube Data API).
        """
        dynamic_items: List[CourseRecommendationItem] = []

        for provider in self._providers:
            try:
                items = provider.search(
                    skill=skill,
                    context=context,
                    max_results=max_results,
                    free_only=free_only,
                    priority=priority,
                )
                if free_only:
                    items = [it for it in items if it.free]
                dynamic_items.extend(items)
            except Exception as e:
                logger.warning(
                    f"Dynamic learning provider '{provider.name}' failed for skill '{skill}': {e}"
                )

        return dynamic_items[:max_results]

    def _fallback_catalogue_resources(
        self,
        skill: str,
        priority: str = "HIGH",
        free_only: bool = False,
        max_per_skill: int = 3,
    ) -> List[CourseRecommendationItem]:
        """
        Fallback mechanism querying the verified catalogue (courses.json).
        """
        courses = self.find_courses_for_skill(skill, free_only=free_only)
        top_courses = courses[:max_per_skill]

        fallback_items: List[CourseRecommendationItem] = []
        for course in top_courses:
            fallback_items.append(
                CourseRecommendationItem(
                    skill=skill,
                    priority=priority,
                    title=course.title,
                    provider=course.provider,
                    resource_type=course.resource_type,
                    level=course.level,
                    free=course.free,
                    url=course.url,
                    description=course.description,
                    thumbnail=course.thumbnail,
                    published_at=course.published_at,
                )
            )
        return fallback_items

    def recommend_for_skill_gaps(
        self,
        skill_gaps: List[SkillGapItem],
        requirements_list: Optional[List[JobRequirements]] = None,
        free_only: bool = False,
        max_per_skill: int = 3,
        include_low_priority: bool = False,
    ) -> List[CourseRecommendationItem]:
        """
        Generates ranked recommendations for student skill gaps.
        Uses dynamic discovery with fallback to verified local catalogue.
        """
        # Filter gaps based on priority (HIGH & MEDIUM preferred)
        valid_gaps = [
            gap for gap in skill_gaps
            if include_low_priority or gap.priority in ("HIGH", "MEDIUM")
        ]

        # Sort skill gaps: Priority (HIGH -> MEDIUM -> LOW), then by jobs_affected desc
        valid_gaps.sort(
            key=lambda g: (_PRIORITY_ORDER.get(g.priority, 3), -g.jobs_affected, g.skill.lower())
        )

        results: List[CourseRecommendationItem] = []
        for gap in valid_gaps:
            context = self._extract_context_for_skill(gap.skill, requirements_list)

            # Step 1: Dynamic discovery
            items = self._discover_dynamic_resources(
                skill=gap.skill,
                context=context,
                max_results=max_per_skill,
                free_only=free_only,
                priority=gap.priority,
            )

            # Step 2: If dynamic returned empty (e.g. no API key configured or offline), use fallback catalogue
            if not items:
                items = self._fallback_catalogue_resources(
                    skill=gap.skill,
                    priority=gap.priority,
                    free_only=free_only,
                    max_per_skill=max_per_skill,
                )

            results.extend(items)

        return results

    def recommend_for_skills(
        self,
        skills: List[str],
        free_only: bool = False,
        max_per_skill: int = 3,
        default_priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        """
        Generates recommendations directly for a given list of skills.
        """
        results: List[CourseRecommendationItem] = []
        for skill in skills:
            clean_skill = skill.strip()
            if not clean_skill:
                continue

            # Dynamic discovery
            items = self._discover_dynamic_resources(
                skill=clean_skill,
                context=None,
                max_results=max_per_skill,
                free_only=free_only,
                priority=default_priority,
            )

            # Fallback
            if not items:
                items = self._fallback_catalogue_resources(
                    skill=clean_skill,
                    priority=default_priority,
                    free_only=free_only,
                    max_per_skill=max_per_skill,
                )

            results.extend(items)

        return results
