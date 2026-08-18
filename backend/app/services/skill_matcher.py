"""
Skill matching service.

Compares candidate skills (direct + project + experience) against
JobRequirements.required_skills and preferred_skills.

Normalisation handles obvious casing and minor phrasing differences;
it deliberately avoids overly aggressive fuzzy matching.
"""
import re
from typing import List, Set

from app.models.resume import CandidateProfile
from app.models.job_requirements import JobRequirements
from app.models.matching import SkillMatchResult

# ---------------------------------------------------------------------------
# Synonyms / aliases: each entry is a frozenset of equivalent skill strings.
# Keep this list conservative — only add when equivalence is certain.
# ---------------------------------------------------------------------------
_SKILL_ALIASES: List[frozenset] = [
    frozenset({"python", "python 3", "python3", "python programming"}),
    frozenset({"javascript", "js", "node.js", "nodejs"}),
    frozenset({"typescript", "ts"}),
    frozenset({"react", "react.js", "reactjs"}),
    frozenset({"angular", "angularjs", "angular.js"}),
    frozenset({"vue", "vue.js", "vuejs"}),
    frozenset({"sql", "mysql", "postgresql", "postgres", "sqlite"}),
    frozenset({"rest", "rest api", "restful", "restful api", "rest apis"}),
    frozenset({"docker", "containerisation", "containerization"}),
    frozenset({"kubernetes", "k8s"}),
    frozenset({"machine learning", "ml"}),
    frozenset({"deep learning", "dl"}),
    frozenset({"natural language processing", "nlp"}),
    frozenset({"git", "version control", "github", "gitlab"}),
    frozenset({"aws", "amazon web services"}),
    frozenset({"gcp", "google cloud", "google cloud platform"}),
    frozenset({"azure", "microsoft azure"}),
    frozenset({"fastapi", "fast api"}),
    frozenset({"django", "django rest framework", "drf"}),
    frozenset({"flask", "flask api"}),
    frozenset({"c++", "cpp"}),
    frozenset({"c#", "csharp", "c sharp"}),
    frozenset({"html", "html5"}),
    frozenset({"css", "css3", "sass", "scss"}),
    frozenset({"java", "java se", "java ee"}),
    frozenset({"spring", "spring boot"}),
    frozenset({"mongodb", "mongo"}),
    frozenset({"redis", "redis cache"}),
    frozenset({"linux", "unix"}),
    frozenset({"agile", "scrum", "kanban"}),
]


def _normalise(skill: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    s = skill.lower().strip()
    s = re.sub(r"[^\w\s\.\+\#]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _canonical(skill: str) -> str:
    """Return a canonical form — the lowest-sorted alias in its alias group, if any."""
    norm = _normalise(skill)
    for group in _SKILL_ALIASES:
        if norm in group:
            return sorted(group)[0]
    return norm


def _collect_candidate_skills(candidate: CandidateProfile) -> Set[str]:
    """
    Gather all skills the candidate demonstrates:
    - direct skills list
    - skills from each experience entry
    - technologies from each project
    """
    skills: Set[str] = set()
    for s in candidate.skills:
        skills.add(_canonical(s))
    for exp in candidate.experience:
        for s in (exp.skills or []):
            skills.add(_canonical(s))
    for proj in candidate.projects:
        for t in (proj.technologies or []):
            skills.add(_canonical(t))
    return skills


def match_skills(
    candidate: CandidateProfile,
    requirements: JobRequirements,
) -> SkillMatchResult:
    """
    Compare candidate skills against required and preferred skills.
    Returns normalised scores in [0, 100].
    """
    cand_skills = _collect_candidate_skills(candidate)

    required = [_canonical(s) for s in requirements.required_skills]
    preferred = [_canonical(s) for s in requirements.preferred_skills]

    matched_req = [s for s in required if s in cand_skills]
    missing_req = [s for s in required if s not in cand_skills]
    matched_pref = [s for s in preferred if s in cand_skills]
    missing_pref = [s for s in preferred if s not in cand_skills]

    req_score = (len(matched_req) / len(required) * 100) if required else 100.0
    pref_score = (len(matched_pref) / len(preferred) * 100) if preferred else 100.0

    # Return human-readable (original-casing) skill names where possible
    def _display(canonical_list: List[str], source: List[str]) -> List[str]:
        """Map canonical names back to the original casing from the source list."""
        disp = []
        for c in canonical_list:
            original = next((s for s in source if _canonical(s) == c), c)
            disp.append(original)
        return disp

    return SkillMatchResult(
        matched_required_skills=_display(matched_req, requirements.required_skills),
        missing_required_skills=_display(missing_req, requirements.required_skills),
        matched_preferred_skills=_display(matched_pref, requirements.preferred_skills),
        missing_preferred_skills=_display(missing_pref, requirements.preferred_skills),
        required_skill_score=round(req_score, 2),
        preferred_skill_score=round(pref_score, 2),
    )
