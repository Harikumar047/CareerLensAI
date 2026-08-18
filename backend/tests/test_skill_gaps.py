"""
Tests for Skill Gap Analysis feature.
"""
import json
import uuid
import pytest
from unittest.mock import patch
from fastapi import status

from app.models.resume import CandidateProfile, Project, Experience
from app.models.job_requirements import JobRequirements
from app.models.skill_gap import SkillGapItem, SkillGapResponse
from app.services.skill_gap_analyzer import analyze_skill_gaps, determine_priority
from app.config import settings


# ---------------------------------------------------------------------------
# Unit tests: Priority calculation
# ---------------------------------------------------------------------------

def test_determine_priority():
    assert determine_priority(65.0) == "HIGH"
    assert determine_priority(50.0) == "HIGH"
    assert determine_priority(49.9) == "MEDIUM"
    assert determine_priority(25.0) == "MEDIUM"
    assert determine_priority(24.9) == "LOW"
    assert determine_priority(0.0) == "LOW"


# ---------------------------------------------------------------------------
# Unit tests: Skill Gap Analysis Logic
# ---------------------------------------------------------------------------

def test_analyze_skill_gaps_empty_jobs():
    candidate = CandidateProfile(name="Test", skills=["Python", "SQL"])
    gaps = analyze_skill_gaps(candidate, [])
    assert gaps == []


def test_analyze_skill_gaps_no_gaps():
    candidate = CandidateProfile(name="Test", skills=["Python", "SQL", "Docker"])
    reqs = [
        JobRequirements(job_id="j1", required_skills=["Python", "SQL"]),
        JobRequirements(job_id="j2", required_skills=["Docker"]),
    ]
    gaps = analyze_skill_gaps(candidate, reqs)
    assert gaps == []


def test_analyze_skill_gaps_with_frequencies_and_priorities():
    # Candidate knows Python, SQL, Java
    candidate = CandidateProfile(
        name="Student",
        skills=["Python", "SQL", "Java"],
    )

    # 20 jobs total
    # 13 jobs require AWS
    # 10 jobs require Docker
    # 4 jobs require Kubernetes
    reqs = []
    for i in range(20):
        req_skills = ["Python"]
        pref_skills = []
        if i < 13:
            req_skills.append("AWS")
        if i < 10:
            pref_skills.append("Docker")
        if i < 4:
            req_skills.append("Kubernetes")
        reqs.append(JobRequirements(job_id=f"j_{i}", required_skills=req_skills, preferred_skills=pref_skills))

    gaps = analyze_skill_gaps(candidate, reqs)

    assert len(gaps) == 3
    # Top gap should be AWS
    assert gaps[0].skill == "AWS"
    assert gaps[0].jobs_affected == 13
    assert gaps[0].percentage == 65.0
    assert gaps[0].priority == "HIGH"

    # Second gap should be Docker
    assert gaps[1].skill == "Docker"
    assert gaps[1].jobs_affected == 10
    assert gaps[1].percentage == 50.0
    assert gaps[1].priority == "HIGH"

    # Third gap should be Kubernetes
    assert gaps[2].skill == "Kubernetes"
    assert gaps[2].jobs_affected == 4
    assert gaps[2].percentage == 20.0
    assert gaps[2].priority == "LOW"


def test_analyze_skill_gaps_considers_projects_and_experience():
    # Candidate doesn't have Docker in skills list, but has it in projects
    candidate = CandidateProfile(
        name="Student",
        skills=["Python"],
        projects=[Project(name="API", technologies=["Docker"])],
        experience=[Experience(company="Acme", skills=["SQL"])],
    )
    reqs = [
        JobRequirements(job_id="j1", required_skills=["Python", "Docker", "SQL", "AWS"]),
    ]
    gaps = analyze_skill_gaps(candidate, reqs)

    # Only AWS should be missing
    assert len(gaps) == 1
    assert gaps[0].skill == "AWS"
    assert gaps[0].jobs_affected == 1
    assert gaps[0].percentage == 100.0


def test_analyze_skill_gaps_alias_handling():
    # Candidate lists 'python3' and 'js'
    candidate = CandidateProfile(
        name="Student",
        skills=["python3", "js"],
    )
    # Job lists 'Python' and 'JavaScript'
    reqs = [
        JobRequirements(job_id="j1", required_skills=["Python", "JavaScript", "Redis"]),
    ]
    gaps = analyze_skill_gaps(candidate, reqs)

    # Only Redis should be detected as missing
    assert len(gaps) == 1
    assert gaps[0].skill == "Redis"


# ---------------------------------------------------------------------------
# API tests: POST /api/skills/gaps
# ---------------------------------------------------------------------------

def test_api_skill_gaps_not_found(client):
    response = client.post("/api/skills/gaps", json={
        "resume_id": "nonexistent_resume",
        "search_id": "nonexistent_search",
    })
    assert response.status_code == status.HTTP_404_NOT_FOUND


@patch("app.services.job_parser.JobParserService.parse_job_requirements")
def test_api_skill_gaps_success(mock_parse, client):
    # 1. Setup candidate profile
    resume_id = str(uuid.uuid4())
    profile = CandidateProfile(
        name="Jane Dev",
        skills=["Python", "SQL"],
    )
    profile_path = settings.RESUMES_DIR / f"{resume_id}.json"
    profile_path.write_text(profile.model_dump_json(), encoding="utf-8")

    # 2. Setup cached job search
    search_id = str(uuid.uuid4())
    search_data = {
        "search_id": search_id,
        "source": "adzuna",
        "search_parameters": {"role": "backend", "location": "Remote"},
        "jobs": [
            {"id": "j1", "source": "adzuna", "title": "Backend Dev", "description": "Python, Docker"},
            {"id": "j2", "source": "adzuna", "title": "Senior Backend", "description": "Python, AWS, Docker"},
        ],
    }
    search_path = settings.JOBS_DIR / f"search_{search_id}.json"
    search_path.write_text(json.dumps(search_data), encoding="utf-8")

    # 3. Mock job parser
    mock_parse.side_effect = [
        JobRequirements(job_id="j1", required_skills=["Python", "Docker"]),
        JobRequirements(job_id="j2", required_skills=["Python", "AWS", "Docker"]),
    ]

    # 4. Call endpoint
    response = client.post("/api/skills/gaps", json={
        "resume_id": resume_id,
        "search_id": search_id,
    })

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["resume_id"] == resume_id
    assert data["search_id"] == search_id
    assert data["total_jobs_analyzed"] == 2
    assert len(data["skill_gaps"]) == 2

    # Docker is required by 2 jobs (100% -> HIGH)
    assert data["skill_gaps"][0]["skill"] == "Docker"
    assert data["skill_gaps"][0]["jobs_affected"] == 2
    assert data["skill_gaps"][0]["percentage"] == 100.0
    assert data["skill_gaps"][0]["priority"] == "HIGH"

    # AWS is required by 1 job (50% -> HIGH)
    assert data["skill_gaps"][1]["skill"] == "AWS"
    assert data["skill_gaps"][1]["jobs_affected"] == 1
    assert data["skill_gaps"][1]["percentage"] == 50.0
    assert data["skill_gaps"][1]["priority"] == "HIGH"

    # Cleanup
    profile_path.unlink(missing_ok=True)
    search_path.unlink(missing_ok=True)
