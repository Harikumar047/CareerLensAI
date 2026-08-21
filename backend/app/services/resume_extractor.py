import json
import logging
import re
from typing import Dict, Any, Optional, List
from app.models.resume import CandidateProfile, Education, Experience, Project

logger = logging.getLogger(__name__)

# Common technology keywords to match from resume text
TECH_SKILLS_CATALOG = {
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "c", "ruby", "php", "swift",
    "kotlin", "go", "golang", "rust", "scala", "r", "dart", "sql", "html", "css", "html5", "css3",
    # Frameworks & Libraries
    "react", "react.js", "reactjs", "next.js", "nextjs", "vue", "vue.js", "angular", "angularjs",
    "node", "node.js", "nodejs", "express", "express.js", "fastapi", "flask", "django",
    "spring", "spring boot", "laravel", "rails", "asp.net", "graphql", "rest api", "rest",
    # Databases & Caching
    "postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis", "elasticsearch",
    "cassandra", "firebase", "supabase", "dynamodb", "mariadb", "oracle",
    # Cloud, DevOps & Tools
    "docker", "kubernetes", "k8s", "aws", "amazon web services", "azure", "gcp",
    "google cloud", "git", "github", "gitlab", "ci/cd", "jenkins", "terraform", "linux", "unix",
    # Data Science / ML / AI
    "machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch",
    "keras", "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn", "tableau", "power bi"
}

PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
EMAIL_PATTERN = re.compile(r"[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}")


class ResumeExtractorService:
    """
    Lightweight, high-performance rule-based extractor.
    Extracts structured CandidateProfile directly from resume text using
    regular expressions, section splitting, and entity extraction.
    Zero PyTorch / zero external API dependencies with < 40MB memory footprint.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ResumeExtractorService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

    def load_model(self) -> None:
        """No-op for lightweight extractor."""
        logger.info("Lightweight ResumeExtractor initialized.")

    @property
    def is_loaded(self) -> bool:
        return True

    def _extract_name(self, lines: List[str]) -> Optional[str]:
        for line in lines[:6]:
            cleaned = line.strip()
            if not cleaned or len(cleaned) > 50:
                continue
            if "@" in cleaned or re.search(r"\d", cleaned) or "resume" in cleaned.lower() or "curriculum" in cleaned.lower():
                continue
            words = cleaned.split()
            if 1 <= len(words) <= 4:
                return cleaned
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        match = EMAIL_PATTERN.search(text)
        return match.group(0).strip() if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = PHONE_PATTERN.search(text)
        return match.group(0).strip() if match else None

    def _extract_skills(self, text: str) -> List[str]:
        text_lower = text.lower()
        found = set()
        for skill in TECH_SKILLS_CATALOG:
            pattern = r"(?:\b|_)" + re.escape(skill) + r"(?:\b|_)"
            if re.search(pattern, text_lower):
                found.add(skill.title() if len(skill) > 3 else skill.upper())
        return sorted(list(found))

    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        edu_list: List[Dict[str, Any]] = []
        edu_keywords = ["bachelor", "b.tech", "b.e", "b.sc", "bs", "master", "m.tech", "m.sc", "mba", "phd", "diploma"]
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        for line in lines:
            line_l = line.lower()
            for kw in edu_keywords:
                if kw in line_l:
                    year_match = re.search(r"\b(19|20)\d{2}\b", line)
                    year = int(year_match.group(0)) if year_match else None
                    edu_list.append({
                        "degree": line[:60],
                        "institution": "",
                        "graduation_year": year,
                        "field_of_study": ""
                    })
                    break
        return edu_list

    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        exp_list: List[Dict[str, Any]] = []
        exp_roles = ["engineer", "developer", "intern", "manager", "lead", "analyst", "designer", "architect"]
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        
        for line in lines:
            line_l = line.lower()
            for role in exp_roles:
                if role in line_l and len(line) < 80:
                    years = re.findall(r"\b(19|20)\d{2}\b", line)
                    start_date = years[0] if len(years) > 0 else ""
                    end_date = years[1] if len(years) > 1 else ("Present" if "present" in line_l else "")
                    exp_list.append({
                        "role": line,
                        "company": "",
                        "start_date": start_date,
                        "end_date": end_date,
                        "description": "",
                        "skills": []
                    })
                    break
        return exp_list

    def extract_candidate_profile(self, text: str) -> CandidateProfile:
        if not text or not text.strip():
            raise ValueError("Resume text is empty.")

        clean_text = text.strip()
        lines = [l.strip() for l in clean_text.split("\n") if l.strip()]

        name = self._extract_name(lines)
        email = self._extract_email(clean_text)
        phone = self._extract_phone(clean_text)
        skills = self._extract_skills(clean_text)
        education = self._extract_education(clean_text)
        experience = self._extract_experience(clean_text)

        profile_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "location": None,
            "skills": skills,
            "experience": experience,
            "education": education,
            "projects": [],
            "certifications": [],
            "total_experience_years": len(experience) * 1.5 if experience else None,
            "preferred_roles": []
        }

        return CandidateProfile(**profile_data)