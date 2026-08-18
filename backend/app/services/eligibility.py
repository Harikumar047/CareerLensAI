"""
Eligibility service.

Checks a candidate against hard job requirements.
Semantic similarity does NOT override decisions made here.
"""
from typing import Optional
from app.models.resume import CandidateProfile
from app.models.job_requirements import JobRequirements
from app.models.matching import EligibilityResult


def check_eligibility(
    candidate: CandidateProfile,
    requirements: JobRequirements,
) -> EligibilityResult:
    """
    Evaluate whether a candidate meets the hard requirements of a job.

    Hard failures cause eligible=False.
    Soft warnings are recorded in reasons but do not fail eligibility.
    """
    reasons: list[str] = []
    hard_failures: list[str] = []
    eligible = True

    candidate_years = candidate.total_experience_years or 0.0
    min_exp = requirements.min_experience_years
    max_exp = requirements.max_experience_years

    # ------------------------------------------------------------------
    # 1. Experience check
    # ------------------------------------------------------------------
    if min_exp is not None and min_exp > 0:
        if candidate_years < min_exp:
            hard_failures.append(
                f"Requires {min_exp}+ years experience; candidate has {candidate_years}."
            )
            eligible = False
        else:
            reasons.append(
                f"Experience requirement met ({candidate_years}y ≥ {min_exp}y)."
            )
    else:
        # Entry-level / no minimum
        reasons.append("No minimum experience required — open to all levels.")

    if max_exp is not None and max_exp > 0:
        if candidate_years > max_exp + 2:   # allow 2-year grace
            reasons.append(
                f"Candidate may be over-experienced ({candidate_years}y vs max {max_exp}y)."
            )

    # ------------------------------------------------------------------
    # 2. Education check (only if explicitly required)
    # ------------------------------------------------------------------
    edu_reqs = [r.lower() for r in requirements.education_requirements]
    if edu_reqs:
        candidate_degrees = [
            (e.degree or "").lower() + " " + (e.field_of_study or "").lower()
            for e in candidate.education
        ]
        edu_keywords = [
            "bachelor", "b.tech", "b.e", "bs", "b.sc",
            "master", "m.tech", "m.sc", "mba", "phd",
            "degree", "graduate",
        ]

        # If the requirement mentions "mandatory" or "required" explicitly
        hard_edu_required = any(
            kw in req for req in edu_reqs
            for kw in ("mandatory", "required", "must have", "must hold")
        )

        if hard_edu_required and not candidate.education:
            hard_failures.append("Education requirement is explicitly mandatory; candidate has no education listed.")
            eligible = False
        elif candidate.education:
            # Soft check: try to find a rough match
            matched_edu = False
            for req in edu_reqs:
                for cand_deg in candidate_degrees:
                    # Match on shared meaningful words (degree level / field)
                    req_words = set(req.split()) - {"in", "or", "a", "an", "the"}
                    cand_words = set(cand_deg.split())
                    if req_words & cand_words:
                        matched_edu = True
                        break
                # Also accept any listed degree keyword overlap
                if any(kw in req for kw in edu_keywords):
                    if any(any(kw in cd for kw in edu_keywords) for cd in candidate_degrees):
                        matched_edu = True
                if matched_edu:
                    break
            if matched_edu:
                reasons.append("Education appears to match stated requirements.")
            else:
                reasons.append("Education may not precisely match stated requirements (soft warning).")
        else:
            reasons.append("No candidate education listed; cannot verify education requirement.")

    # ------------------------------------------------------------------
    # 3. Location check (only a hard fail if "only" / "must" is present)
    # ------------------------------------------------------------------
    job_location = (requirements.location or "").lower()
    if job_location:
        cand_location = (candidate.location or "").lower()
        hard_location = any(
            kw in job_location for kw in ("only", "must", "on-site required", "in-person")
        )
        if hard_location and cand_location and job_location not in cand_location:
            if "remote" not in cand_location and "remote" not in job_location:
                hard_failures.append(
                    f"Job requires on-site in '{requirements.location}'; candidate location is '{candidate.location}'."
                )
                eligible = False
        elif cand_location and job_location in cand_location:
            reasons.append(f"Location matches: {requirements.location}.")
        else:
            reasons.append("Location not verified — may be flexible or remote.")

    if not hard_failures:
        eligible = True

    return EligibilityResult(
        eligible=eligible,
        reasons=reasons,
        hard_failures=hard_failures,
    )
