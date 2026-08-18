"""
Skill Gap Analyzer Service.

Identifies skills that are required or preferred across target jobs
which are missing from the candidate's resume/profile.
"""
from typing import List, Dict, Set
from collections import defaultdict

from app.models.resume import CandidateProfile
from app.models.job_requirements import JobRequirements
from app.models.skill_gap import SkillGapItem
from app.services.skill_matcher import _collect_candidate_skills, _canonical


def determine_priority(percentage: float) -> str:
    """
    Determine priority based on percentage of jobs requiring the skill:
    - HIGH: >= 50%
    - MEDIUM: >= 25%
    - LOW: < 25%
    """
    if percentage >= 50.0:
        return "HIGH"
    elif percentage >= 25.0:
        return "MEDIUM"
    else:
        return "LOW"


def analyze_skill_gaps(
    candidate: CandidateProfile,
    requirements_list: List[JobRequirements],
) -> List[SkillGapItem]:
    """
    Analyzes missing skills across a list of job requirements for a candidate.

    Args:
        candidate: The candidate's structured profile.
        requirements_list: Structured requirements for each job analyzed.

    Returns:
        List of SkillGapItem objects ranked by frequency/impact (descending).
    """
    total_jobs = len(requirements_list)
    if total_jobs == 0:
        return []

    # Get set of all canonical skills demonstrated by the candidate
    candidate_skills = _collect_candidate_skills(candidate)

    # Track how many jobs each missing skill appears in
    # Key: canonical_skill, Value: set of job_indices or count of jobs
    skill_job_count: Dict[str, int] = defaultdict(int)
    # Maintain display name for canonical representation (pick the most common/original casing)
    skill_display_names: Dict[str, str] = {}

    for req in requirements_list:
        # Combine required and preferred skills for the job
        all_job_skills = req.required_skills + req.preferred_skills
        
        # Deduplicate within the same job so a job only votes once per skill
        job_canonical_skills: Set[str] = set()

        for raw_skill in all_job_skills:
            canon = _canonical(raw_skill)
            if not canon:
                continue

            if canon not in skill_display_names:
                skill_display_names[canon] = raw_skill.strip()

            # If candidate does not have this skill, mark it as missing for this job
            if canon not in candidate_skills:
                job_canonical_skills.add(canon)

        for missing_canon in job_canonical_skills:
            skill_job_count[missing_canon] += 1

    # Convert counts to SkillGapItem list
    results: List[SkillGapItem] = []
    for canon_skill, count in skill_job_count.items():
        percentage = round((count / total_jobs) * 100, 2)
        priority = determine_priority(percentage)
        display_name = skill_display_names.get(canon_skill, canon_skill)

        results.append(
            SkillGapItem(
                skill=display_name,
                jobs_affected=count,
                percentage=percentage,
                priority=priority,
            )
        )

    # Sort: highest jobs_affected first, then by skill name alphabetically
    results.sort(key=lambda item: (-item.jobs_affected, item.skill.lower()))

    return results
