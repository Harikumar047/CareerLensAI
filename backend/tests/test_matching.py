"""
Tests for Milestone 4 — Matching Engine.

All Hugging Face / sentence-transformer model calls are mocked.
No model downloads occur during pytest.
"""
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status

from app.models.resume import CandidateProfile, Education, Experience, Project
from app.models.job import Job
from app.models.job_requirements import JobRequirements
from app.models.matching import JobMatchResult, EligibilityResult, SkillMatchResult
from app.services.eligibility import check_eligibility
from app.services.skill_matcher import match_skills, _canonical
from app.services.matcher import (
    compute_match,
    _experience_score,
    _education_score,
    _project_score,
)
from app.config import settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_candidate(
    skills=None,
    experience_years=None,
    education=None,
    experience=None,
    projects=None,
    location=None,
) -> CandidateProfile:
    return CandidateProfile(
        name="Test Candidate",
        skills=skills or [],
        total_experience_years=experience_years,
        education=education or [],
        experience=experience or [],
        projects=projects or [],
        location=location,
    )


def make_requirements(
    required_skills=None,
    preferred_skills=None,
    min_exp=None,
    max_exp=None,
    edu_reqs=None,
    location=None,
    employment_type=None,
    extracted_keywords=None,
) -> JobRequirements:
    return JobRequirements(
        job_id="test_job_001",
        required_skills=required_skills or [],
        preferred_skills=preferred_skills or [],
        min_experience_years=min_exp,
        max_experience_years=max_exp,
        education_requirements=edu_reqs or [],
        location=location,
        employment_type=employment_type,
        extracted_keywords=extracted_keywords or [],
    )


def make_job(job_id="adzuna_001", title="Software Developer", description="Python, SQL, REST API development role.") -> Job:
    return Job(
        id=job_id,
        source="adzuna",
        title=title,
        description=description,
    )


# ---------------------------------------------------------------------------
# 1. Skill matching — exact match
# ---------------------------------------------------------------------------

def test_exact_skill_match():
    candidate = make_candidate(skills=["Python", "SQL", "FastAPI"])
    req = make_requirements(required_skills=["Python", "SQL", "FastAPI"])
    result = match_skills(candidate, req)
    assert result.required_skill_score == 100.0
    assert result.missing_required_skills == []


# ---------------------------------------------------------------------------
# 2. Partial skill match
# ---------------------------------------------------------------------------

def test_partial_skill_match():
    candidate = make_candidate(skills=["Python"])
    req = make_requirements(required_skills=["Python", "SQL", "Docker"])
    result = match_skills(candidate, req)
    assert 0 < result.required_skill_score < 100
    assert "SQL" in result.missing_required_skills or "sql" in [s.lower() for s in result.missing_required_skills]


# ---------------------------------------------------------------------------
# 3. Missing required skill
# ---------------------------------------------------------------------------

def test_missing_required_skill():
    candidate = make_candidate(skills=["Java"])
    req = make_requirements(required_skills=["Python", "SQL"])
    result = match_skills(candidate, req)
    assert result.required_skill_score == 0.0
    assert len(result.missing_required_skills) == 2


# ---------------------------------------------------------------------------
# 4. Preferred skill gap
# ---------------------------------------------------------------------------

def test_preferred_skill_gap():
    candidate = make_candidate(skills=["Python", "SQL"])
    req = make_requirements(
        required_skills=["Python"],
        preferred_skills=["AWS", "Docker"],
    )
    result = match_skills(candidate, req)
    assert result.required_skill_score == 100.0
    assert result.preferred_skill_score == 0.0
    assert "AWS" in result.missing_preferred_skills


# ---------------------------------------------------------------------------
# 5. Fresher + 0-2 years job
# ---------------------------------------------------------------------------

def test_fresher_entry_level_job():
    candidate = make_candidate(experience_years=0.0)
    req = make_requirements(min_exp=0.0, max_exp=2.0)
    score = _experience_score(candidate, req)
    assert score == 100.0

    eligibility = check_eligibility(candidate, req)
    assert eligibility.eligible is True


# ---------------------------------------------------------------------------
# 6. Fresher + 3-5 years job (hard fail)
# ---------------------------------------------------------------------------

def test_fresher_senior_job_hard_fail():
    candidate = make_candidate(experience_years=0.0)
    req = make_requirements(min_exp=3.0, max_exp=5.0)
    eligibility = check_eligibility(candidate, req)
    assert eligibility.eligible is False
    assert len(eligibility.hard_failures) > 0


# ---------------------------------------------------------------------------
# 7. Education match
# ---------------------------------------------------------------------------

def test_education_match():
    candidate = make_candidate(
        education=[Education(degree="B.Tech", field_of_study="Computer Science", graduation_year=2022)]
    )
    req = make_requirements(edu_reqs=["Bachelor's in Computer Science"])
    score = _education_score(candidate, req)
    assert score > 50.0


# ---------------------------------------------------------------------------
# 8. Education mismatch
# ---------------------------------------------------------------------------

def test_education_mismatch_no_education():
    candidate = make_candidate(education=[])
    req = make_requirements(edu_reqs=["Bachelor's degree required"])
    score = _education_score(candidate, req)
    assert score == 0.0


# ---------------------------------------------------------------------------
# 9. Project relevance
# ---------------------------------------------------------------------------

def test_project_relevance():
    candidate = make_candidate(
        projects=[Project(
            name="E-commerce API",
            description="Built with Python and FastAPI with SQL database",
            technologies=["Python", "FastAPI", "SQL"],
        )]
    )
    req = make_requirements(
        required_skills=["Python", "REST API", "SQL"],
        extracted_keywords=["backend", "api", "python"],
    )
    score = _project_score(candidate, req)
    # Python + SQL are in the project's technologies and map to required_skills.
    # FastAPI canonicalises differently from "REST API", so 2 of 3 skills match = ~53% tech score.
    # Without an embedding service, only the deterministic tech overlap is scored.
    assert score > 20.0


# ---------------------------------------------------------------------------
# 10. Semantic similarity (mocked)
# ---------------------------------------------------------------------------

def test_semantic_similarity_mocked():
    mock_svc = MagicMock()
    mock_svc.is_loaded = True
    mock_svc.calculate_similarity.return_value = 0.82

    from app.services.matcher import _semantic_score
    candidate = make_candidate(skills=["Python", "REST API"])
    job = make_job()
    score = _semantic_score(candidate, job, mock_svc)
    assert score == pytest.approx(82.0, abs=1.0)


# ---------------------------------------------------------------------------
# 11. Fit-score calculation
# ---------------------------------------------------------------------------

def test_fit_score_calculation():
    mock_svc = MagicMock()
    mock_svc.is_loaded = True
    mock_svc.calculate_similarity.return_value = 0.80

    candidate = make_candidate(
        skills=["Python", "SQL", "FastAPI"],
        experience_years=2.0,
        education=[Education(degree="B.Tech", field_of_study="Computer Science", graduation_year=2022)],
        projects=[Project(name="REST API project", description="FastAPI REST API with SQL", technologies=["Python", "FastAPI", "SQL"])],
    )
    req = make_requirements(
        required_skills=["Python", "SQL"],
        preferred_skills=["FastAPI"],
        min_exp=0.0, max_exp=3.0,
        edu_reqs=["Bachelor's in Computer Science"],
    )
    job = make_job()
    result = compute_match(candidate, job, req, mock_svc)
    assert result.eligible is True
    assert result.fit_score > 70.0


# ---------------------------------------------------------------------------
# 12. Ineligible candidate (below min_exp)
# ---------------------------------------------------------------------------

def test_ineligible_candidate():
    candidate = make_candidate(experience_years=0.0)
    req = make_requirements(min_exp=5.0)
    job = make_job()
    result = compute_match(candidate, job, req)
    assert result.eligible is False
    assert "Not recommended" in result.recommendation
    assert len(result.hard_failures) > 0


# ---------------------------------------------------------------------------
# 13. Strong match
# ---------------------------------------------------------------------------

def test_strong_match_recommendation():
    mock_svc = MagicMock()
    mock_svc.is_loaded = True
    mock_svc.calculate_similarity.return_value = 0.90

    candidate = make_candidate(
        skills=["Python", "SQL", "REST API", "Docker"],
        experience_years=2.0,
        education=[Education(degree="B.Tech", field_of_study="Computer Science")],
        projects=[Project(name="API Service", technologies=["Python", "SQL", "REST API", "Docker"])],
    )
    req = make_requirements(
        required_skills=["Python", "SQL", "REST API", "Docker"],
        min_exp=0.0, max_exp=3.0,
    )
    result = compute_match(candidate, make_job(), req, mock_svc)
    assert result.eligible is True
    assert result.fit_score >= 75.0
    assert "Strong match" in result.recommendation


# ---------------------------------------------------------------------------
# 14. Medium match
# ---------------------------------------------------------------------------

def test_medium_match_recommendation():
    mock_svc = MagicMock()
    mock_svc.is_loaded = True
    mock_svc.calculate_similarity.return_value = 0.5

    candidate = make_candidate(skills=["Python"], experience_years=1.0)
    req = make_requirements(
        required_skills=["Python", "SQL", "Docker", "Kubernetes"],
        min_exp=0.0, max_exp=3.0,
    )
    result = compute_match(candidate, make_job(), req, mock_svc)
    assert result.eligible is True
    assert result.fit_score < 75.0


# ---------------------------------------------------------------------------
# 15. Low match
# ---------------------------------------------------------------------------

def test_low_match():
    candidate = make_candidate(skills=["Java"], experience_years=1.0)
    req = make_requirements(
        required_skills=["Python", "Go", "Rust", "Kubernetes", "AWS"],
        min_exp=0.0, max_exp=3.0,
    )
    result = compute_match(candidate, make_job(), req)
    assert result.fit_score < 50.0
    assert "Low match" in result.recommendation or "Worth" in result.recommendation


# ---------------------------------------------------------------------------
# 16. API — analyze single job (mocked)
# ---------------------------------------------------------------------------

@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_api_analyze_single_job(mock_parse, client):
    """
    Create a stored profile and a cached search, then call the analyze endpoint.
    """
    # Store a profile
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Ana Dev", skills=["Python", "SQL"], total_experience_years=2.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    # Store a mock search containing one job
    search_id = str(uuid.uuid4())
    mock_job = {
        "id": "adzuna_test_001",
        "source": "adzuna",
        "title": "Python Developer",
        "description": "Python and SQL backend role",
    }
    search_data = {
        "search_id": search_id,
        "search_parameters": {"role": "developer", "location": "Chennai"},
        "source": "adzuna",
        "jobs": [mock_job],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    # Mock job parser to return simple requirements
    mock_parse.return_value = JobRequirements(
        job_id="adzuna_test_001",
        required_skills=["Python", "SQL"],
        min_experience_years=0.0,
        max_experience_years=3.0,
    )

    response = client.post("/api/matching/analyze", json={
        "resume_id": resume_id,
        "job_id": "adzuna_test_001",
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["job_id"] == "adzuna_test_001"
    assert "fit_score" in data
    assert "eligible" in data

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)
    for f in settings.JOBS_DIR.glob("matches_*.json"):
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 17. API — analyze entire search (mocked)
# ---------------------------------------------------------------------------

@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_api_analyze_search(mock_parse, client):
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Sam Eng", skills=["Python", "Docker"], total_experience_years=1.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    mock_jobs = [
        {"id": "adzuna_j1", "source": "adzuna", "title": "Python Dev", "description": "Python role"},
        {"id": "adzuna_j2", "source": "adzuna", "title": "Java Dev", "description": "Java role"},
    ]
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "search_parameters": {"role": "developer", "location": "Remote"},
        "jobs": mock_jobs,
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.side_effect = [
        JobRequirements(job_id="adzuna_j1", required_skills=["Python"], min_experience_years=0.0, max_experience_years=2.0),
        JobRequirements(job_id="adzuna_j2", required_skills=["Java"], min_experience_years=0.0, max_experience_years=2.0),
    ]

    response = client.post("/api/matching/analyze-search", json={
        "resume_id": resume_id,
        "search_id": search_id,
    })
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_jobs"] == 2
    assert "matches" in data
    assert len(data["matches"]) == 2

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)
    for f in settings.JOBS_DIR.glob("matches_*.json"):
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 18. Ranking — eligible jobs appear before ineligible
# ---------------------------------------------------------------------------

@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_ranking_order(mock_parse, client):
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(
        name="Junior Dev",
        skills=["Python"],
        total_experience_years=0.5,
    )
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "search_parameters": {},
        "jobs": [
            {"id": "senior_job", "source": "adzuna", "title": "Senior Engineer", "description": "Senior role"},
            {"id": "junior_job", "source": "adzuna", "title": "Junior Developer", "description": "Entry role"},
        ],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.side_effect = [
        JobRequirements(job_id="senior_job", required_skills=["Python"], min_experience_years=5.0),
        JobRequirements(job_id="junior_job", required_skills=["Python"], min_experience_years=0.0, max_experience_years=2.0),
    ]

    response = client.post("/api/matching/analyze-search", json={
        "resume_id": resume_id,
        "search_id": search_id,
    })
    assert response.status_code == status.HTTP_200_OK
    matches = response.json()["matches"]
    # junior_job should be first (eligible), senior_job last (ineligible)
    assert matches[0]["job_id"] == "junior_job"
    assert matches[1]["job_id"] == "senior_job"
    assert matches[0]["eligible"] is True
    assert matches[1]["eligible"] is False

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)
    for f in settings.JOBS_DIR.glob("matches_*.json"):
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 19. Persistence — match file is written
# ---------------------------------------------------------------------------

@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_match_persistence(mock_parse, client):
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="P Dev", skills=["Python"], total_experience_years=1.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    search_data = {
        "search_id": search_id, "source": "adzuna", "search_parameters": {},
        "jobs": [{"id": "adzuna_persist", "source": "adzuna", "title": "Dev", "description": "Python dev"}],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")
    mock_parse.return_value = JobRequirements(job_id="adzuna_persist", required_skills=["Python"])

    before = set(settings.JOBS_DIR.glob("matches_*.json"))
    client.post("/api/matching/analyze-search", json={"resume_id": resume_id, "search_id": search_id})
    after = set(settings.JOBS_DIR.glob("matches_*.json"))

    new_files = after - before
    assert len(new_files) >= 1
    stored = json.loads(next(iter(new_files)).read_text())
    assert stored["resume_id"] == resume_id

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)
    for f in after:
        f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 20. Skill normalisation
# ---------------------------------------------------------------------------

def test_skill_normalisation():
    assert _canonical("Python 3") == _canonical("python")
    assert _canonical("python programming") == _canonical("Python")
    assert _canonical("REST API") == _canonical("restful api")
    assert _canonical("Node.js") == _canonical("nodejs")


# ---------------------------------------------------------------------------
# 21. What-If Skill Simulator Tests (M6)
# ---------------------------------------------------------------------------

@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_what_if_simulation_one_missing_skill(mock_parse, client):
    """
    Test simulating adding one missing required skill (e.g. AWS).
    Score must increase, and improvement must match simulated_score - current_score.
    """
    # 1. Setup candidate with Python
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Sim Candidate", skills=["Python"], total_experience_years=2.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    # 2. Setup job requiring Python, AWS, Docker
    search_id = str(uuid.uuid4())
    job_id = f"job_{uuid.uuid4()}"
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "search_parameters": {},
        "jobs": [{"id": job_id, "source": "adzuna", "title": "Cloud Dev", "description": "Need Python, AWS, Docker"}],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.return_value = JobRequirements(
        job_id=job_id,
        required_skills=["Python", "AWS", "Docker"],
    )

    # 3. Simulate adding AWS
    response = client.post("/api/matching/what-if", json={
        "resume_id": resume_id,
        "job_id": job_id,
        "skills_to_add": ["AWS"],
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["job_id"] == job_id
    assert data["skills_added"] == ["AWS"]
    assert "AWS" in data["newly_matched_skills"]
    assert "Docker" in data["remaining_gaps"]
    assert data["improvement"] > 0
    assert round(data["simulated_score"] - data["current_score"], 2) == data["improvement"]
    assert "AWS" in data["explanation"]

    # 4. Verify stored resume profile was NOT modified
    saved_profile = CandidateProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    assert saved_profile.skills == ["Python"]
    assert "AWS" not in saved_profile.skills

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)


@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_what_if_simulation_multiple_skills(mock_parse, client):
    """
    Test simulating adding multiple missing required skills (AWS + Docker).
    """
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Sim Dev", skills=["Python"], total_experience_years=2.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    job_id = f"job_{uuid.uuid4()}"
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "jobs": [{"id": job_id, "source": "adzuna", "title": "Cloud Dev", "description": "Need Python, AWS, Docker"}],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.return_value = JobRequirements(
        job_id=job_id,
        required_skills=["Python", "AWS", "Docker"],
    )

    response = client.post("/api/matching/what-if", json={
        "resume_id": resume_id,
        "job_id": job_id,
        "skills_to_add": ["AWS", "Docker"],
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["skills_added"] == ["AWS", "Docker"]
    assert "AWS" in data["newly_matched_skills"]
    assert "Docker" in data["newly_matched_skills"]
    assert len(data["remaining_gaps"]) == 0
    assert data["improvement"] > 0
    assert data["simulated_score"] > data["current_score"]

    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)


@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_what_if_simulation_already_present_skill(mock_parse, client):
    """
    Test simulating adding a skill the candidate already has (e.g. Python).
    Improvement should be 0.0.
    """
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Python Dev", skills=["Python"], total_experience_years=2.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    job_id = f"job_{uuid.uuid4()}"
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "jobs": [{"id": job_id, "source": "adzuna", "title": "Python Dev", "description": "Need Python"}],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.return_value = JobRequirements(job_id=job_id, required_skills=["Python"])

    response = client.post("/api/matching/what-if", json={
        "resume_id": resume_id,
        "job_id": job_id,
        "skills_to_add": ["Python"],
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["improvement"] == 0.0
    assert data["current_score"] == data["simulated_score"]
    assert data["newly_matched_skills"] == []

    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)


@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_what_if_empty_skills_list(mock_parse, client):
    """
    Test submitting empty skills_to_add list. Score should not change.
    """
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(name="Empty Sim", skills=["Python"], total_experience_years=2.0)
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    search_id = str(uuid.uuid4())
    job_id = f"job_{uuid.uuid4()}"
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "jobs": [{"id": job_id, "source": "adzuna", "title": "Dev", "description": "Need Python"}],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    mock_parse.return_value = JobRequirements(job_id=job_id, required_skills=["Python"])

    response = client.post("/api/matching/what-if", json={
        "resume_id": resume_id,
        "job_id": job_id,
        "skills_to_add": [],
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["improvement"] == 0.0
    assert data["current_score"] == data["simulated_score"]

    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)


def test_what_if_invalid_ids(client):
    """
    Test 404 error responses for invalid resume_id or job_id.
    """
    # 1. Invalid resume
    res1 = client.post("/api/matching/what-if", json={
        "resume_id": "nonexistent_resume_123",
        "job_id": "some_job_123",
        "skills_to_add": ["AWS"],
    })
    assert res1.status_code == status.HTTP_404_NOT_FOUND

    # 2. Valid resume but non-existent job
    resume_id = str(uuid.uuid4())
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(CandidateProfile(name="Test").model_dump_json(), encoding="utf-8")

    res2 = client.post("/api/matching/what-if", json={
        "resume_id": resume_id,
        "job_id": "nonexistent_job_999",
        "skills_to_add": ["AWS"],
    })
    assert res2.status_code == status.HTTP_404_NOT_FOUND

    profile_path.unlink(missing_ok=True)

