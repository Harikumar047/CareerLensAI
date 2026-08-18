"""
Tests for Course & Learning Resource Recommendation Feature (M5 - Real Resources).

Covers:
- YouTube & Coursera real resources
- Exact skill matching
- Multiple skill gaps & priority ordering (HIGH -> MEDIUM -> LOW)
- Beginner suitability & free-course filtering
- No matching course handling
- Invalid resume/search IDs (404 handling)
- Missing parameter handling (400 handling)
- Direct skills list recommendations
- API response validation (POST & GET) with real clickable URLs
"""
import json
import uuid
import pytest
from unittest.mock import patch
from fastapi import status

from app.config import settings
from app.models.course import Course, CourseRecommendationItem, CourseRecommendationResponse
from app.models.job_requirements import JobRequirements
from app.models.resume import CandidateProfile
from app.models.skill_gap import SkillGapItem
from app.services.course_recommender import CourseRecommenderService


# ---------------------------------------------------------------------------
# Unit tests: CourseRecommenderService
# ---------------------------------------------------------------------------

def test_catalogue_loaded_and_valid():
    """Verify that all items in the catalogue have real URLs and valid resource types."""
    service = CourseRecommenderService()
    courses = service.get_all_courses()
    assert len(courses) > 0
    for c in courses:
        assert c.id
        assert c.skill
        assert c.title
        assert c.provider
        assert c.resource_type in ("youtube", "coursera")
        assert c.level in ("beginner", "intermediate", "advanced")
        assert isinstance(c.free, bool)
        assert c.url.startswith("https://")
        assert ("youtube.com" in c.url) or ("coursera.org" in c.url)
        assert c.description


def test_exact_and_canonical_skill_matching():
    """Verify exact and alias skill matching (e.g. AWS, Python, JS -> JavaScript)."""
    service = CourseRecommenderService()

    # Direct match
    aws_courses = service.find_courses_for_skill("AWS")
    assert len(aws_courses) > 0
    assert any(c.skill == "AWS" for c in aws_courses)

    # Alias / case-insensitive match (e.g. 'js' -> 'JavaScript')
    js_courses = service.find_courses_for_skill("js")
    assert len(js_courses) > 0
    assert any(c.skill == "JavaScript" for c in js_courses)


def test_resource_type_filtering():
    """Verify filtering by resource_type ('youtube' vs 'coursera')."""
    service = CourseRecommenderService()
    yt_courses = service.find_courses_for_skill("AWS", resource_type="youtube")
    assert len(yt_courses) > 0
    assert all(c.resource_type == "youtube" for c in yt_courses)

    coursera_courses = service.find_courses_for_skill("AWS", resource_type="coursera")
    assert len(coursera_courses) > 0
    assert all(c.resource_type == "coursera" for c in coursera_courses)


def test_ranking_beginner_and_free_priority():
    """
    Verify ranking order for a skill with mixed levels and free/paid options:
    Beginner free courses should rank highest.
    """
    service = CourseRecommenderService()
    aws_courses = service.find_courses_for_skill("AWS")
    assert len(aws_courses) >= 2

    first_course = aws_courses[0]
    assert first_course.level == "beginner"
    assert first_course.free is True
    assert first_course.resource_type == "youtube"


def test_free_course_filtering():
    """Verify filtering only free courses when free_only=True."""
    service = CourseRecommenderService()
    free_courses = service.find_courses_for_skill("AWS", free_only=True)
    assert len(free_courses) > 0
    for c in free_courses:
        assert c.free is True


def test_no_matching_course():
    """Verify handling when no courses exist in catalogue for a skill."""
    service = CourseRecommenderService()
    obscure_courses = service.find_courses_for_skill("ObscureLegacyLanguage999")
    assert obscure_courses == []

    gap = SkillGapItem(
        skill="ObscureLegacyLanguage999",
        jobs_affected=5,
        percentage=50.0,
        priority="HIGH",
    )
    recs = service.recommend_for_skill_gaps([gap])
    assert recs == []


def test_multiple_skill_gaps_and_priority_ordering():
    """
    Verify multiple skill gaps are ranked with HIGH priority before MEDIUM priority,
    and LOW priority gaps are excluded by default.
    """
    service = CourseRecommenderService()

    gaps = [
        SkillGapItem(skill="Kubernetes", jobs_affected=3, percentage=15.0, priority="LOW"),
        SkillGapItem(skill="Docker", jobs_affected=8, percentage=40.0, priority="MEDIUM"),
        SkillGapItem(skill="AWS", jobs_affected=15, percentage=75.0, priority="HIGH"),
    ]

    recs = service.recommend_for_skill_gaps(gaps)

    # LOW is filtered out by default; HIGH comes before MEDIUM
    assert len(recs) >= 2
    assert recs[0].skill == "AWS"
    assert recs[0].priority == "HIGH"
    assert recs[0].url.startswith("https://")

    # Second group should be Docker (MEDIUM)
    docker_items = [r for r in recs if r.skill == "Docker"]
    assert len(docker_items) > 0
    assert docker_items[0].priority == "MEDIUM"


def test_recommend_for_skills_direct_list():
    """Verify direct list of skills recommendations."""
    service = CourseRecommenderService()
    recs = service.recommend_for_skills(["FastAPI", "Docker"], free_only=True, max_per_skill=1)

    assert len(recs) == 2
    assert recs[0].skill == "FastAPI"
    assert recs[0].free is True
    assert recs[0].url.startswith("https://")

    assert recs[1].skill == "Docker"
    assert recs[1].free is True
    assert recs[1].url.startswith("https://")


# ---------------------------------------------------------------------------
# API Route tests: /api/courses
# ---------------------------------------------------------------------------

def test_api_list_courses(client):
    """Test GET /api/courses returns list of courses."""
    response = client.get("/api/courses")
    assert response.status_code == status.HTTP_200_OK
    courses = response.json()
    assert isinstance(courses, list)
    assert len(courses) > 0
    assert "title" in courses[0]
    assert "provider" in courses[0]
    assert "resource_type" in courses[0]
    assert "url" in courses[0]


def test_api_list_courses_filtered(client):
    """Test GET /api/courses?skill=Python&free_only=true."""
    response = client.get("/api/courses?skill=Python&free_only=true")
    assert response.status_code == status.HTTP_200_OK
    courses = response.json()
    assert len(courses) > 0
    for c in courses:
        assert c["free"] is True


def test_api_recommendations_invalid_ids(client):
    """Test POST /api/courses/recommendations with non-existent resume or search IDs."""
    res = client.post("/api/courses/recommendations", json={
        "resume_id": "missing_resume_123",
        "search_id": "missing_search_123",
    })
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # Non-existent search
    resume_id = str(uuid.uuid4())
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(CandidateProfile(name="Test").model_dump_json(), encoding="utf-8")

    res_missing_search = client.post("/api/courses/recommendations", json={
        "resume_id": resume_id,
        "search_id": "nonexistent_search",
    })
    assert res_missing_search.status_code == status.HTTP_404_NOT_FOUND

    profile_path.unlink(missing_ok=True)


def test_api_recommendations_missing_input(client):
    """Test POST & GET /api/courses/recommendations with neither resume/search nor skills."""
    res_post = client.post("/api/courses/recommendations", json={})
    assert res_post.status_code == status.HTTP_400_BAD_REQUEST

    res_get = client.get("/api/courses/recommendations")
    assert res_get.status_code == status.HTTP_400_BAD_REQUEST


def test_api_recommendations_from_skills_list_post(client):
    """Test POST /api/courses/recommendations with direct skills list."""
    res = client.post("/api/courses/recommendations", json={
        "skills": ["AWS", "Docker"],
        "free_only": True,
        "max_per_skill": 1,
    })
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "recommendations" in data
    recs = data["recommendations"]
    assert len(recs) == 2

    # Check schema matches user request:
    # { skill, priority, title, provider, resource_type, level, free, url, description }
    aws_item = recs[0]
    assert aws_item["skill"] == "AWS"
    assert aws_item["priority"] == "HIGH"
    assert "title" in aws_item
    assert "provider" in aws_item
    assert aws_item["resource_type"] in ("youtube", "coursera")
    assert aws_item["level"] == "beginner"
    assert aws_item["free"] is True
    assert aws_item["url"].startswith("https://")
    assert "description" in aws_item


def test_api_recommendations_from_skills_list_get(client):
    """Test GET /api/courses/recommendations?skills=AWS&skills=Docker."""
    res = client.get("/api/courses/recommendations?skills=AWS&skills=Docker&free_only=true")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "recommendations" in data
    recs = data["recommendations"]
    assert len(recs) >= 2
    assert recs[0]["skill"] == "AWS"
    assert recs[0]["url"].startswith("https://")


@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_api_recommendations_from_resume_and_search(mock_parse, client):
    """
    End-to-end integration test:
    Candidate with Python -> Searches for jobs requiring AWS (100% HIGH) and Docker (50% HIGH)
    Endpoint should recommend verified YouTube and Coursera courses for AWS and Docker.
    """
    # 1. Setup candidate profile
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(
        name="Candidate A",
        skills=["Python"],
    )
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    # 2. Setup cached job search
    search_id = str(uuid.uuid4())
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "search_parameters": {"role": "Cloud Developer", "location": "Remote"},
        "jobs": [
            {"id": "j1", "source": "adzuna", "title": "AWS Cloud Engineer", "description": "Need AWS and Docker"},
            {"id": "j2", "source": "adzuna", "title": "Cloud Specialist", "description": "Need AWS"},
        ],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    # 3. Mock job parser
    mock_parse.side_effect = [
        JobRequirements(job_id="j1", required_skills=["AWS", "Docker"]),
        JobRequirements(job_id="j2", required_skills=["AWS"]),
    ]

    # 4. Call POST /api/courses/recommendations
    response = client.post("/api/courses/recommendations", json={
        "resume_id": resume_id,
        "search_id": search_id,
        "free_only": False,
        "max_per_skill": 2,
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "recommendations" in data
    recs = data["recommendations"]
    assert len(recs) >= 2

    # AWS: affected 2 jobs (100% -> HIGH)
    aws_items = [r for r in recs if r["skill"] == "AWS"]
    assert len(aws_items) > 0
    assert aws_items[0]["priority"] == "HIGH"
    assert aws_items[0]["url"].startswith("https://")
    assert aws_items[0]["resource_type"] in ("youtube", "coursera")

    # Docker: affected 1 job (50% -> HIGH)
    docker_items = [r for r in recs if r["skill"] == "Docker"]
    assert len(docker_items) > 0
    assert docker_items[0]["priority"] == "HIGH"
    assert docker_items[0]["url"].startswith("https://")

    # 5. Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)


@patch("app.services.youtube_service.YouTubeService.search_learning_resources")
def test_api_recommendations_with_dynamic_provider_results(mock_yt_search, client):
    """
    Test that dynamic provider results take precedence when available.
    """
    dynamic_item = CourseRecommendationItem(
        skill="AWS",
        priority="HIGH",
        title="Dynamic Live AWS Course 2026",
        provider="freeCodeCamp.org",
        resource_type="youtube",
        level="beginner",
        free=True,
        url="https://www.youtube.com/watch?v=dynamic_live_999",
        description="Freshly discovered dynamic tutorial.",
    )
    mock_yt_search.return_value = [dynamic_item]

    res = client.post("/api/courses/recommendations", json={
        "skills": ["AWS"],
        "max_per_skill": 1,
    })

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Dynamic Live AWS Course 2026"
    assert data["recommendations"][0]["url"] == "https://www.youtube.com/watch?v=dynamic_live_999"

