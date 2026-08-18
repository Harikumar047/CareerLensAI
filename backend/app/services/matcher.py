"""
Core matching pipeline.

Combines eligibility, skill match, project relevance, experience, education,
and semantic similarity into a single weighted Fit Score.

Weighting:
  Required skills  : 40 %
  Preferred skills : 15 %
  Projects         : 15 %
  Experience       : 15 %
  Education        : 10 %
  Semantic         :  5 %

IMPORTANT: The Fit Score represents alignment between the candidate's
demonstrated profile and the job description requirements.
It does NOT represent a probability of being shortlisted.
"""
import logging
import re
from typing import List, Optional

from app.models.resume import CandidateProfile
from app.models.job import Job
from app.models.job_requirements import JobRequirements
from app.models.matching import JobMatchResult, EligibilityResult, SkillMatchResult
from app.services.eligibility import check_eligibility
from app.services.skill_matcher import match_skills, _normalise, _canonical

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
W_REQUIRED_SKILLS = 0.40
W_PREFERRED_SKILLS = 0.15
W_PROJECTS = 0.15
W_EXPERIENCE = 0.15
W_EDUCATION = 0.10
W_SEMANTIC = 0.05


# ---------------------------------------------------------------------------
# Experience score
# ---------------------------------------------------------------------------

def _experience_score(
    candidate: CandidateProfile,
    requirements: JobRequirements,
) -> float:
    """
    0–100 score for experience alignment.

    Candidate has already been disqualified by eligibility check if below
    a hard minimum, so here we score *quality of fit* within the window.
    """
    candidate_years = candidate.total_experience_years or 0.0
    min_exp = requirements.min_experience_years
    max_exp = requirements.max_experience_years

    if min_exp is None and max_exp is None:
        return 100.0  # No requirement stated

    lo = min_exp or 0.0
    hi = max_exp or (lo + 5.0)  # infer upper bound if only minimum specified

    if lo == 0.0 and hi <= 2.0:
        # Entry-level: freshers and junior candidates both score well
        if candidate_years <= hi:
            return 100.0
        # Slightly over-experienced
        return max(0.0, 100.0 - (candidate_years - hi) * 10)

    if candidate_years < lo:
        # Below minimum — eligibility should have already caught hard failures
        gap = lo - candidate_years
        return max(0.0, 100.0 - gap * 20)

    if candidate_years > hi + 2:
        # Possibly over-experienced
        excess = candidate_years - (hi + 2)
        return max(50.0, 100.0 - excess * 8)

    return 100.0


# ---------------------------------------------------------------------------
# Education score
# ---------------------------------------------------------------------------

_EDU_LEVEL_KEYWORDS = [
    ("phd", 5),
    ("ph.d", 5),
    ("doctorate", 5),
    ("master", 4),
    ("m.tech", 4),
    ("m.sc", 4),
    ("mba", 4),
    ("bachelor", 3),
    ("b.tech", 3),
    ("b.e", 3),
    ("bs", 3),
    ("b.sc", 3),
    ("associate", 2),
    ("diploma", 2),
]


def _edu_level(text: str) -> int:
    t = text.lower()
    for kw, level in _EDU_LEVEL_KEYWORDS:
        if kw in t:
            return level
    return 0


def _education_score(
    candidate: CandidateProfile,
    requirements: JobRequirements,
) -> float:
    """0–100 score for education alignment."""
    edu_reqs = [r.lower() for r in requirements.education_requirements]
    if not edu_reqs:
        return 100.0  # No requirement stated

    if not candidate.education:
        return 0.0

    # Try to find any overlapping education keyword
    cand_texts = [
        f"{e.degree or ''} {e.field_of_study or ''}".lower()
        for e in candidate.education
    ]

    # Field-of-study match
    field_keywords = set()
    for req in edu_reqs:
        for word in req.split():
            if len(word) > 3 and word not in {"with", "from", "degree", "science", "engineering"}:
                field_keywords.add(word)

    field_match = any(
        any(kw in ct for kw in field_keywords)
        for ct in cand_texts
    )

    # Degree-level match
    req_level = max((_edu_level(r) for r in edu_reqs), default=0)
    cand_level = max((_edu_level(ct) for ct in cand_texts), default=0)

    if req_level == 0:
        # Vague requirement (e.g., "relevant degree")
        level_score = 100.0 if cand_level > 0 else 50.0
    elif cand_level >= req_level:
        level_score = 100.0
    elif cand_level == req_level - 1:
        level_score = 70.0
    elif cand_level > 0:
        level_score = 40.0
    else:
        level_score = 0.0

    field_bonus = 20.0 if field_match else 0.0
    return min(100.0, level_score + field_bonus) if level_score > 0 else level_score


# ---------------------------------------------------------------------------
# Project relevance score
# ---------------------------------------------------------------------------

def _project_score(
    candidate: CandidateProfile,
    requirements: JobRequirements,
    embedding_service=None,
) -> float:
    """
    0–100 score reflecting how relevant the candidate's projects are to the job.

    Primary signal: technology overlap with required/preferred skills.
    Secondary signal: semantic similarity of project description to job keywords
                      (only if embedding service is available and loaded).
    """
    if not candidate.projects:
        return 0.0

    all_req_skills = set(_canonical(s) for s in requirements.required_skills)
    all_pref_skills = set(_canonical(s) for s in requirements.preferred_skills)
    all_keywords = set(_canonical(k) for k in requirements.extracted_keywords)
    target_skills = all_req_skills | all_pref_skills | all_keywords

    if not target_skills:
        return 50.0  # No target info — neutral score

    best_score = 0.0
    for proj in candidate.projects:
        proj_techs = set(_canonical(t) for t in (proj.technologies or []))
        tech_overlap = proj_techs & target_skills
        tech_score = (len(tech_overlap) / len(target_skills)) * 100.0 if target_skills else 0.0

        # Optional semantic boost
        sem_score = 0.0
        if (embedding_service and embedding_service.is_loaded
                and proj.description and requirements.extracted_keywords):
            try:
                job_context = " ".join(requirements.extracted_keywords)
                raw_sim = embedding_service.calculate_similarity(proj.description, job_context)
                sem_score = raw_sim * 100.0
            except Exception:
                sem_score = 0.0

        proj_total = tech_score * 0.8 + sem_score * 0.2
        best_score = max(best_score, proj_total)

    return round(min(100.0, best_score), 2)


# ---------------------------------------------------------------------------
# Semantic similarity (profile vs job)
# ---------------------------------------------------------------------------

def _semantic_score(
    candidate: CandidateProfile,
    job: Job,
    embedding_service,
) -> float:
    """
    Cosine similarity between the candidate's skill-set and the job description.
    Returns 0–100. Returns 0 if model is not loaded.
    """
    if not embedding_service or not embedding_service.is_loaded:
        return 0.0
    try:
        cand_text = " ".join(candidate.skills)
        job_text = f"{job.title} {job.description or ''}"
        sim = embedding_service.calculate_similarity(cand_text, job_text)
        return round(sim * 100.0, 2)
    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# Recommendation label
# ---------------------------------------------------------------------------

def _recommend(eligible: bool, fit_score: float) -> str:
    if not eligible:
        return "Not recommended — does not meet one or more hard requirements."
    if fit_score >= 75:
        return "Strong match"
    if fit_score >= 50:
        return "Worth considering"
    return "Low match"


# ---------------------------------------------------------------------------
# Strength / gap narrative
# ---------------------------------------------------------------------------

def _narrative(
    candidate: CandidateProfile,
    requirements: JobRequirements,
    skill_result: SkillMatchResult,
    exp_score: float,
    edu_score: float,
    eligible: bool,
    eligibility: EligibilityResult,
) -> tuple[list[str], list[str]]:
    strengths: list[str] = []
    gaps: list[str] = []

    if skill_result.matched_required_skills:
        strengths.append(
            f"Matches {len(skill_result.matched_required_skills)} required skill(s): "
            + ", ".join(skill_result.matched_required_skills[:5])
        )
    if skill_result.matched_preferred_skills:
        strengths.append(
            f"Also has preferred skill(s): "
            + ", ".join(skill_result.matched_preferred_skills[:3])
        )
    if exp_score >= 90:
        strengths.append("Experience aligns well with the role requirements.")
    if edu_score >= 80:
        strengths.append("Education matches stated requirements.")
    if candidate.projects:
        strengths.append(
            f"Has {len(candidate.projects)} project(s) demonstrating practical skills."
        )

    if skill_result.missing_required_skills:
        gaps.append(
            f"Missing required skill(s): "
            + ", ".join(skill_result.missing_required_skills[:5])
        )
    if skill_result.missing_preferred_skills:
        gaps.append(
            f"Preferred but not demonstrated: "
            + ", ".join(skill_result.missing_preferred_skills[:3])
        )
    for failure in eligibility.hard_failures:
        gaps.append(failure)
    if edu_score < 50 and requirements.education_requirements:
        gaps.append("Education may not fully match stated requirements.")

    return strengths, gaps


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_match(
    candidate: CandidateProfile,
    job: Job,
    requirements: JobRequirements,
    embedding_service=None,
) -> JobMatchResult:
    """
    Run the full matching pipeline and return a JobMatchResult.

    This score is a Job Fit Score — it represents alignment between the
    candidate's demonstrated profile and this job description.
    It does not guarantee or predict recruiter shortlisting.
    """
    # 1. Hard eligibility
    eligibility = check_eligibility(candidate, requirements)

    # 2. Skill matching
    skill_result = match_skills(candidate, requirements)

    # 3. Sub-scores
    exp_score = _experience_score(candidate, requirements)
    edu_score = _education_score(candidate, requirements)
    proj_score = _project_score(candidate, requirements, embedding_service)
    sem_score = _semantic_score(candidate, job, embedding_service)

    # 4. Weighted Fit Score
    fit_score = round(
        skill_result.required_skill_score * W_REQUIRED_SKILLS
        + skill_result.preferred_skill_score * W_PREFERRED_SKILLS
        + proj_score * W_PROJECTS
        + exp_score * W_EXPERIENCE
        + edu_score * W_EDUCATION
        + sem_score * W_SEMANTIC,
        2,
    )

    # 5. Narrative
    strengths, gaps = _narrative(
        candidate, requirements, skill_result,
        exp_score, edu_score, eligibility.eligible, eligibility,
    )

    return JobMatchResult(
        job_id=job.id,
        eligible=eligibility.eligible,
        fit_score=fit_score,
        required_skill_score=skill_result.required_skill_score,
        preferred_skill_score=skill_result.preferred_skill_score,
        project_score=proj_score,
        experience_score=round(exp_score, 2),
        education_score=round(edu_score, 2),
        semantic_score=sem_score,
        matched_skills=skill_result.matched_required_skills + skill_result.matched_preferred_skills,
        missing_required_skills=skill_result.missing_required_skills,
        missing_preferred_skills=skill_result.missing_preferred_skills,
        strengths=strengths,
        gaps=gaps,
        recommendation=_recommend(eligibility.eligible, fit_score),
        eligibility_reasons=eligibility.reasons,
        hard_failures=eligibility.hard_failures,
    )
