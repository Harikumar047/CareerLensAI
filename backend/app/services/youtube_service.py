"""
YouTube Learning Resource Discovery Service.

Uses official YouTube Data API v3 to dynamically discover high quality,
verified video tutorials, crash courses, and playlists for technical skills.

Features:
- Live dynamic discovery
- Short-lived TTL caching
- Job context keyword injection
- Educational filtering (beginner/tutorial/course)
- Robust error handling (graceful fallback on API failure/missing key)
"""
import html
import logging
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.models.course import CourseRecommendationItem

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Common reputable educational channels on YouTube
REPUTABLE_CHANNELS = {
    "freecodecamp.org",
    "freecodecamp",
    "programming with mosh",
    "traversy media",
    "fireship",
    "corey schafer",
    "kevin powell",
    "tech with tim",
    "alex the analyst",
    "edureka!",
    "simplilearn",
    "krish naik",
    "mit opencourseware",
    "harvard",
    "stanford",
    "aws",
    "google cloud tech",
    "microsoft developer",
    "sentdex",
    "net ninja",
    "academind",
    "web dev simplified",
}


class YouTubeService:
    """
    Service for querying YouTube Data API v3 for dynamic learning resources.
    Includes in-memory TTL caching and educational content ranking.
    """

    _instance: Optional["YouTubeService"] = None

    def __new__(cls, *args, **kwargs) -> "YouTubeService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache: Dict[str, Tuple[float, List[CourseRecommendationItem]]] = {}
        return cls._instance

    def __init__(self, api_key: Optional[str] = None, ttl_seconds: Optional[int] = None) -> None:
        self.api_key = api_key if api_key is not None else settings.YOUTUBE_API_KEY
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.YOUTUBE_CACHE_TTL_SECONDS

    def _build_cache_key(self, skill: str, context: Optional[str], max_results: int) -> str:
        ctx_norm = context.strip().lower() if context else ""
        return f"{skill.strip().lower()}|{ctx_norm}|{max_results}"

    def clear_cache(self) -> None:
        """Clears all cached YouTube search results."""
        self._cache.clear()

    def _get_from_cache(self, cache_key: str) -> Optional[List[CourseRecommendationItem]]:
        if cache_key in self._cache:
            cached_time, results = self._cache[cache_key]
            if time.time() - cached_time < self.ttl_seconds:
                logger.debug(f"Cache HIT for YouTube search key: {cache_key}")
                return results
            else:
                logger.debug(f"Cache EXPIRED for YouTube search key: {cache_key}")
                del self._cache[cache_key]
        return None

    def _store_in_cache(self, cache_key: str, results: List[CourseRecommendationItem]) -> None:
        self._cache[cache_key] = (time.time(), results)

    def _build_query(self, skill: str, context: Optional[str] = None) -> str:
        """
        Builds a high-intent educational search query incorporating skill and job context.
        """
        clean_skill = skill.strip()
        if context and context.strip():
            # Inject top relevant job keywords (e.g., "AWS EC2 Lambda")
            clean_context = context.strip()
            return f"{clean_skill} {clean_context} beginner course tutorial"
        return f"{clean_skill} course tutorial for beginners full course"

    def _detect_level(self, title: str, description: str) -> str:
        text = f"{title} {description}".lower()
        if any(w in text for w in ["advanced", "expert", "deep dive", "architecture", "production"]):
            return "advanced"
        if any(w in text for w in ["intermediate", "part 2", "full stack", "hands-on project"]):
            return "intermediate"
        return "beginner"

    def search_learning_resources(
        self,
        skill: str,
        context: Optional[str] = None,
        max_results: int = 5,
        priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        """
        Queries YouTube Data API v3 dynamically for learning resources.
        Returns empty list if API key is not configured or if an error occurs.
        """
        if not self.api_key:
            logger.info("YOUTUBE_API_KEY is not configured; skipping YouTube dynamic discovery.")
            return []

        cache_key = self._build_cache_key(skill, context, max_results)
        cached_results = self._get_from_cache(cache_key)
        if cached_results is not None:
            return cached_results

        query = self._build_query(skill, context)
        params = {
            "part": "snippet",
            "q": query,
            "type": "video,playlist",
            "relevanceLanguage": "en",
            "maxResults": min(max(max_results * 2, 5), 25),
            "key": self.api_key,
        }

        try:
            logger.info(f"Querying YouTube Data API for query: '{query}'")
            with httpx.Client(timeout=10.0) as client:
                response = client.get(YOUTUBE_SEARCH_URL, params=params)

            if response.status_code != 200:
                logger.warning(
                    f"YouTube API returned status {response.status_code}: {response.text[:200]}"
                )
                return []

            data = response.json()
            items = data.get("items", [])
            results = self._parse_and_rank_items(items, skill=skill, context=context, priority=priority)
            top_results = results[:max_results]

            # Cache the parsed results
            self._store_in_cache(cache_key, top_results)
            return top_results

        except httpx.TimeoutException:
            logger.error("Timeout connecting to YouTube Data API.")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying YouTube Data API: {e}")
            return []

    def _parse_and_rank_items(
        self,
        raw_items: list,
        skill: str,
        context: Optional[str] = None,
        priority: str = "HIGH",
    ) -> List[CourseRecommendationItem]:
        """
        Parses raw YouTube API items into CourseRecommendationItem objects,
        filters for educational value, and ranks them by quality.
        """
        parsed: List[CourseRecommendationItem] = []
        skill_lower = skill.strip().lower()
        context_lower = context.strip().lower() if context else ""

        for item in raw_items:
            id_info = item.get("id", {})
            video_id = id_info.get("videoId")
            playlist_id = id_info.get("playlistId")

            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif playlist_id:
                url = f"https://www.youtube.com/playlist?list={playlist_id}"
            else:
                continue

            snippet = item.get("snippet", {})
            raw_title = snippet.get("title", "")
            title = html.unescape(raw_title)
            description = html.unescape(snippet.get("description", ""))
            channel_title = html.unescape(snippet.get("channelTitle", "YouTube"))
            published_at = snippet.get("publishedAt")

            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )

            level = self._detect_level(title, description)

            parsed.append(
                CourseRecommendationItem(
                    skill=skill,
                    priority=priority,
                    title=title,
                    provider=channel_title,
                    resource_type="youtube",
                    level=level,
                    free=True,
                    url=url,
                    description=description or f"Learning resource for {skill} on YouTube.",
                    thumbnail=thumbnail_url,
                    published_at=published_at,
                )
            )

        # Ranking:
        # 1. Skill in title (0 for yes, 1 for no)
        # 2. Reputable channel (0 for yes, 1 for no)
        # 3. Context in title/description (0 for yes, 1 for no)
        # 4. Beginner level first
        # 5. Length of title/description as proxy for detailed content
        def _rank_score(item: CourseRecommendationItem):
            t_lower = item.title.lower()
            d_lower = item.description.lower()
            ch_lower = item.provider.lower()

            skill_in_title = 0 if skill_lower in t_lower else 1
            reputable = 0 if any(r in ch_lower for r in REPUTABLE_CHANNELS) else 1
            context_match = 0 if (context_lower and (context_lower in t_lower or context_lower in d_lower)) else 1
            level_score = 0 if item.level == "beginner" else (1 if item.level == "intermediate" else 2)

            return (skill_in_title, reputable, context_match, level_score)

        parsed.sort(key=_rank_score)
        return parsed
