import logging
import re
from typing import Optional
from app.models.job import Job
from app.models.job_requirements import JobRequirements
from app.services.resume_extractor import TECH_SKILLS_CATALOG

logger = logging.getLogger(__name__)

class JobParserService:
    """
    Lightweight, fast rule-based job requirement parser.
    Zero PyTorch or GPU dependencies.
    """

    _instance: Optional["JobParserService"] = None

    def __new__(cls) -> "JobParserService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self) -> None:
        """No-op for lightweight parser."""
        logger.info("Lightweight JobParserService initialized.")

    def parse_job_requirements(self, job: Job) -> JobRequirements:
        jd_text = f"{job.title} {job.description or ''}".strip().lower()

        if not jd_text:
            return JobRequirements(job_id=job.id)

        # 1. Extract required skills from text
        found_skills = []
        for skill in TECH_SKILLS_CATALOG:
            pattern = r"(?:\b|_)" + re.escape(skill) + r"(?:\b|_)"
            if re.search(pattern, jd_text):
                found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

        # 2. Extract experience years (e.g., "2-5 years", "3+ years")
        exp_match = re.search(r"(\d+)(?:\s*(?:to|-)\s*(\d+))?\s*(?:\+)?\s*(?:years|yrs)", jd_text)
        min_exp = None
        max_exp = None
        if exp_match:
            try:
                min_exp = float(exp_match.group(1))
                if exp_match.group(2):
                    max_exp = float(exp_match.group(2))
            except (ValueError, TypeError):
                pass

        # 3. Extract education requirements
        edu_reqs = []
        for kw in ["bachelor", "master", "phd", "b.tech", "b.e", "computer science", "engineering"]:
            if kw in jd_text:
                edu_reqs.append(kw.title())

        # Distribute skills: first 70% as required, remainder as preferred
        split_idx = max(1, int(len(found_skills) * 0.7))
        req_skills = found_skills[:split_idx]
        pref_skills = found_skills[split_idx:]

        return JobRequirements(
            job_id=job.id,
            required_skills=req_skills,
            preferred_skills=pref_skills,
            min_experience_years=min_exp,
            max_experience_years=max_exp,
            education_requirements=edu_reqs,
            location=job.location if hasattr(job, 'location') else None,
            employment_type=None,
            extracted_keywords=found_skills[:10]
        )
