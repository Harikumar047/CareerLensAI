import json
import logging
import re
from typing import Dict, Any, Optional, List
from app.models.resume import CandidateProfile, Education, Experience, Project

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy module-level imports for ML libraries.
# Imported here (not inside methods) so that unit tests can patch them via
#   mock.patch("app.services.resume_extractor.AutoModelForCausalLM", ...)
# The try/except means the server still starts even if torch is not installed,
# and load_model() will raise a clear RuntimeError at inference time.
# ---------------------------------------------------------------------------
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    AutoModelForCausalLM = None  # type: ignore[assignment,misc]
    AutoTokenizer = None  # type: ignore[assignment,misc]
    PeftModel = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------
BASE_MODEL_ID = "numind/NuExtract-tiny-v1.5"
ADAPTER_MODEL_ID = "nimendraai/NuExtract-tiny-Resume-Data-Extractor"

# ---------------------------------------------------------------------------
# Template schema — matches the adapter's training schema exactly.
# ---------------------------------------------------------------------------
TEMPLATE_SCHEMA = {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "website": "",
    "skills": [""],
    "experience": [
        {
            "title": "",
            "company": "",
            "duration": "",
            "description": ""
        }
    ],
    "education": [
        {
            "degree": "",
            "institution": "",
            "year": ""
        }
    ],
    "other_details": [""],
}

# ---------------------------------------------------------------------------
# Common technology keywords that should NEVER be treated as companies/roles/dates
# ---------------------------------------------------------------------------
TECH_KEYWORDS = {
    "react", "node", "node.js", "express", "express.js", "postgresql", "mysql",
    "mongodb", "sqlite", "redis", "python", "java", "javascript", "typescript",
    "c++", "c#", "ruby", "php", "swift", "kotlin", "go", "rust", "scala",
    "html", "css", "sass", "less", "tailwind", "bootstrap", "vue", "angular",
    "next.js", "nuxt", "django", "flask", "fastapi", "spring", "spring boot",
    "laravel", "rails", "graphql", "rest", "docker", "kubernetes", "aws",
    "azure", "gcp", "git", "github", "gitlab", "linux", "nginx", "apache",
    "tensorflow", "pytorch", "keras", "pandas", "numpy", "scikit-learn",
    "sql", "nosql", "firebase", "supabase", "prisma", "sequelize",
}

# ---------------------------------------------------------------------------
# Patterns that look like phone numbers (should never go into location/dates)
# ---------------------------------------------------------------------------
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-\(\)]{7,}$")

# ---------------------------------------------------------------------------
# Patterns that look like email addresses
# ---------------------------------------------------------------------------
EMAIL_PATTERN = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")

# ---------------------------------------------------------------------------
# Patterns that look like URLs
# ---------------------------------------------------------------------------
URL_PATTERN = re.compile(r"(https?://|www\.|github\.com|linkedin\.com)", re.IGNORECASE)


class ResumeExtractorService:
    """
    Loads the NuExtract-tiny-v1.5 base model and applies the
    nimendraai/NuExtract-tiny-Resume-Data-Extractor LoRA adapter via PEFT.

    After model inference, every extracted value is validated against the
    original raw resume text. Any value that cannot be found in the source
    text is discarded — preventing hallucinations from leaking into the
    final CandidateProfile.
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
        self.model = None
        self.tokenizer = None
        self.device = None
        self._initialized = True

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Loads the base NuExtract-tiny-v1.5 model, then applies the
        nimendraai LoRA adapter using PEFT. Idempotent — safe to call
        multiple times; the model is loaded only once.
        """
        if self.model is not None:
            return

        if torch is None or AutoModelForCausalLM is None or PeftModel is None:
            raise RuntimeError(
                "Required ML libraries (torch, transformers, peft) are not installed."
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self.device == "cuda" else torch.float32

        logger.info(
            "Loading base model '%s' on device '%s'…", BASE_MODEL_ID, self.device
        )

        try:
            # Step 1 — load base model
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL_ID,
                torch_dtype=dtype,
                trust_remote_code=True,
                device_map="auto" if self.device == "cuda" else None,
            )
            if self.device == "cpu":
                base_model = base_model.to("cpu")

            # Step 2 — load tokenizer from the adapter repo
            self.tokenizer = AutoTokenizer.from_pretrained(
                ADAPTER_MODEL_ID, trust_remote_code=True
            )

            # Step 3 — apply LoRA adapter
            logger.info("Applying LoRA adapter '%s'…", ADAPTER_MODEL_ID)
            self.model = PeftModel.from_pretrained(
                base_model,
                ADAPTER_MODEL_ID,
            )
            self.model.eval()

            logger.info("Resume extraction model ready.")

        except Exception as e:
            logger.error("Failed to load resume extraction model: %s", e)
            self.model = None
            self.tokenizer = None
            raise RuntimeError(f"Model loading failed: {e}") from e

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------------
    # JSON extraction helpers
    # ------------------------------------------------------------------

    def _extract_first_json(self, text: str) -> str:
        """
        Brace-counting extractor — returns the first complete JSON object
        found in text, or the partial JSON from the first opening brace.
        """
        depth = 0
        start: Optional[int] = None
        for i, ch in enumerate(text):
            if ch == "{":
                if start is None:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start : i + 1]
        if start is not None:
            return text[start:].strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text.strip()

    def _repair_truncated_json(self, text: str) -> str:
        """
        Attempts to close an incomplete (truncated) JSON string by
        tracking open brackets/braces and appending the missing closers.
        """
        text = text.rstrip()
        text = re.sub(r",\s*$", "", text)

        stack = []
        in_string = False
        escape_next = False

        for ch in text:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch in ("{", "["):
                    stack.append("}" if ch == "{" else "]")
                elif ch in ("}", "]"):
                    if stack and stack[-1] == ch:
                        stack.pop()

        if in_string:
            text += '"'
        text += "".join(reversed(stack))
        return text

    # ------------------------------------------------------------------
    # Grounding helpers — validate extracted values against the source text
    # ------------------------------------------------------------------

    def _normalize_for_search(self, text: str) -> str:
        """Lower-case and collapse whitespace for fuzzy matching."""
        return re.sub(r"\s+", " ", text.lower().strip())

    def _is_present_in_text(self, value: str, raw_text: str) -> bool:
        """
        Returns True if `value` (or a significant portion of it) can be
        found verbatim (case-insensitive) in `raw_text`.

        For multi-word values, we require at least 60% of the words to appear
        in the text within a reasonable window. Single words must match exactly.
        """
        if not value or not value.strip():
            return False

        needle = self._normalize_for_search(value)
        haystack = self._normalize_for_search(raw_text)

        # Direct substring match (fastest path)
        if needle in haystack:
            return True

        # Word-level majority match for multi-word phrases
        words = [w for w in needle.split() if len(w) > 2]
        if not words:
            return False

        matched = sum(1 for w in words if w in haystack)
        ratio = matched / len(words)

        # Require stricter match for short phrases (≤3 words)
        threshold = 0.6 if len(words) > 3 else 1.0
        return ratio >= threshold

    def _looks_like_phone(self, value: str) -> bool:
        return bool(PHONE_PATTERN.match(value.strip())) if value else False

    def _looks_like_email(self, value: str) -> bool:
        return bool(EMAIL_PATTERN.match(value.strip())) if value else False

    def _looks_like_url(self, value: str) -> bool:
        return bool(URL_PATTERN.search(value)) if value else False

    def _looks_like_tech(self, value: str) -> bool:
        return value.strip().lower() in TECH_KEYWORDS if value else False

    def _extract_year(self, value: str) -> Optional[str]:
        """Return the first 4-digit year found in value, or None."""
        if not value:
            return None
        m = re.search(r"\b(19|20)\d{2}\b", value)
        return m.group(0) if m else None

    def _normalize_skill(self, skill: str) -> str:
        """Normalize common skill capitalization variations."""
        mapping = {
            "sql": "SQL",
            "postgresql": "PostgreSQL",
            "mysql": "MySQL",
            "graphql": "GraphQL",
            "mongodb": "MongoDB",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "expressjs": "Express.js",
            "express.js": "Express.js",
            "reactjs": "React.js",
            "react.js": "React.js",
            "nextjs": "Next.js",
            "next.js": "Next.js",
            "typescript": "TypeScript",
            "javascript": "JavaScript",
            "html": "HTML",
            "css": "CSS",
            "java": "Java",
            "python": "Python",
            "git": "Git",
            "github": "GitHub",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "aws": "AWS",
            "gcp": "GCP",
            "azure": "Azure",
            "c++": "C++",
            "c#": "C#",
        }
        return mapping.get(skill.lower().strip(), skill.strip())

    # ------------------------------------------------------------------
    # Core sanitizer — maps adapter output and validates against raw text
    # ------------------------------------------------------------------

    def _sanitize_extracted_data(
        self, data: Dict[str, Any], raw_text: str
    ) -> Dict[str, Any]:
        """
        Maps the adapter's output schema fields to CandidateProfile fields,
        sanitizes types, and validates every extracted value against the
        original resume text.

        Values that cannot be found in the source text are discarded.

        Adapter schema  →  CandidateProfile field
        ─────────────────────────────────────────
        name            →  name
        email           →  email
        phone           →  phone
        location        →  location
        website         →  (ignored)
        skills          →  skills
        experience      →  experience  (title→role, duration→start_date parsed)
        education       →  education   (year→graduation_year)
        other_details   →  certifications
        """
        sanitized: Dict[str, Any] = {}

        # ------------------------------------------------------------------
        # name
        # ------------------------------------------------------------------
        raw_name = data.get("name") or ""
        if raw_name and self._is_present_in_text(raw_name, raw_text):
            sanitized["name"] = raw_name.strip()
        else:
            sanitized["name"] = None

        # ------------------------------------------------------------------
        # email
        # ------------------------------------------------------------------
        raw_email = data.get("email") or ""
        if raw_email and self._looks_like_email(raw_email) and self._is_present_in_text(raw_email, raw_text):
            sanitized["email"] = raw_email.strip()
        else:
            sanitized["email"] = None

        # ------------------------------------------------------------------
        # phone
        # ------------------------------------------------------------------
        raw_phone = data.get("phone") or ""
        if raw_phone and self._looks_like_phone(raw_phone) and self._is_present_in_text(raw_phone, raw_text):
            sanitized["phone"] = raw_phone.strip()
        else:
            sanitized["phone"] = None

        # ------------------------------------------------------------------
        # location — must be a geographic string, not a phone/email/URL/tech
        # ------------------------------------------------------------------
        raw_location = data.get("location") or ""
        if (
            raw_location
            and not self._looks_like_phone(raw_location)
            and not self._looks_like_email(raw_location)
            and not self._looks_like_url(raw_location)
            and not self._looks_like_tech(raw_location)
            and not re.match(r"^\d", raw_location)   # must not start with a digit
            and self._is_present_in_text(raw_location, raw_text)
        ):
            sanitized["location"] = raw_location.strip()
        else:
            sanitized["location"] = None

        # ------------------------------------------------------------------
        # skills — deduplicated, normalized, validated
        # ------------------------------------------------------------------
        raw_skills = data.get("skills", [])
        if not isinstance(raw_skills, list):
            raw_skills = [str(raw_skills)] if raw_skills else []

        seen_skills: set = set()
        clean_skills: List[str] = []
        for s in raw_skills:
            s = str(s).strip()
            if not s:
                continue
            normalized = self._normalize_skill(s)
            key = normalized.lower()
            if key in seen_skills:
                continue
            # Validate: skill must appear in the raw text
            if self._is_present_in_text(normalized, raw_text) or self._is_present_in_text(s, raw_text):
                seen_skills.add(key)
                clean_skills.append(normalized)
        sanitized["skills"] = clean_skills

        # ------------------------------------------------------------------
        # certifications (from other_details) — validated
        # ------------------------------------------------------------------
        raw_other = data.get("other_details", [])
        if not isinstance(raw_other, list):
            raw_other = [str(raw_other)] if raw_other else []

        clean_certs: List[str] = []
        for s in raw_other:
            s = str(s).strip()
            if not s:
                continue
            # Filter out obviously non-certification entries
            if self._looks_like_tech(s):
                continue
            if s.upper() in ("ACADEMIC", "CSE STREAM", "GITHUB", "LINKEDIN"):
                continue
            if self._is_present_in_text(s, raw_text):
                clean_certs.append(s)
        sanitized["certifications"] = clean_certs

        # ------------------------------------------------------------------
        # experience — validated entry by entry
        # ------------------------------------------------------------------
        raw_exp = data.get("experience", [])
        clean_exp: List[Dict[str, Any]] = []

        if isinstance(raw_exp, list):
            for item in raw_exp:
                if not isinstance(item, dict):
                    continue

                company = (item.get("company") or "").strip()
                role = (item.get("title") or item.get("role") or "").strip()
                duration = (item.get("duration") or "").strip()
                description = (item.get("description") or "").strip()

                # ── Guard: company must not be a tech keyword or look like a phone/email
                if self._looks_like_tech(company) or self._looks_like_phone(company) or self._looks_like_email(company):
                    logger.debug("Discarding experience: company '%s' looks like tech/phone/email", company)
                    continue

                # ── Guard: role must not be a tech keyword or phone
                if self._looks_like_tech(role) or self._looks_like_phone(role):
                    logger.debug("Discarding experience: role '%s' looks like tech/phone", role)
                    continue

                # ── Guard: both company and role must appear in the source text
                company_valid = bool(company) and self._is_present_in_text(company, raw_text)
                role_valid = bool(role) and self._is_present_in_text(role, raw_text)

                # Need at least one of company or role to be grounded
                if not company_valid and not role_valid:
                    logger.debug(
                        "Discarding experience: neither company '%s' nor role '%s' found in resume",
                        company, role,
                    )
                    continue

                # ── Parse duration into start_date / end_date
                start_date = ""
                end_date = ""
                if duration:
                    # Guard: duration must not be a tech stack or phone
                    if not self._looks_like_tech(duration) and not self._looks_like_phone(duration):
                        # Try to parse "Month Year - Month Year" or "Year - Year"
                        date_range = re.findall(
                            r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
                            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
                            r"Dec(?:ember)?)\s+\d{4}|\d{4}|Present|Current|Till Date|Ongoing)",
                            duration, re.IGNORECASE
                        )
                        if len(date_range) >= 2:
                            start_date = date_range[0]
                            end_date = date_range[1]
                        elif len(date_range) == 1:
                            start_date = date_range[0]
                        else:
                            # Try plain year range: "2022 - 2024"
                            years = re.findall(r"\b(20\d{2}|19\d{2})\b", duration)
                            if len(years) >= 2:
                                start_date = years[0]
                                end_date = years[1]
                            elif len(years) == 1:
                                start_date = years[0]

                # ── Validate description
                clean_desc = ""
                if description and self._is_present_in_text(description[:40], raw_text):
                    clean_desc = description

                clean_exp.append({
                    "role": role if role_valid else "",
                    "company": company if company_valid else "",
                    "start_date": start_date,
                    "end_date": end_date,
                    "description": clean_desc,
                    "skills": [],
                })

        sanitized["experience"] = clean_exp

        # ------------------------------------------------------------------
        # education — validated entry by entry
        # ------------------------------------------------------------------
        raw_edu = data.get("education", [])
        clean_edu: List[Dict[str, Any]] = []

        if isinstance(raw_edu, list):
            for item in raw_edu:
                if not isinstance(item, dict):
                    continue

                degree = (item.get("degree") or "").strip()
                institution = (item.get("institution") or "").strip()
                raw_year = (item.get("year") or item.get("graduation_year") or "").strip()
                field = (item.get("field_of_study") or "").strip()

                # ── Guard: institution must not be a tech keyword or phone
                if self._looks_like_tech(institution) or self._looks_like_phone(institution):
                    continue

                # ── At least degree or institution must be grounded
                degree_valid = bool(degree) and self._is_present_in_text(degree, raw_text)
                institution_valid = bool(institution) and self._is_present_in_text(institution, raw_text)

                if not degree_valid and not institution_valid:
                    logger.debug(
                        "Discarding education: neither degree '%s' nor institution '%s' found in resume",
                        degree, institution,
                    )
                    continue

                # ── Parse graduation year
                graduation_year: Optional[int] = None
                if raw_year:
                    digits = re.findall(r"\b(19|20)\d{2}\b", str(raw_year))
                    if digits:
                        try:
                            yr = int(digits[0])
                            # Validate the year is in the raw text
                            if str(yr) in raw_text:
                                graduation_year = yr
                        except ValueError:
                            pass

                clean_edu.append({
                    "degree": degree if degree_valid else "",
                    "institution": institution if institution_valid else "",
                    "graduation_year": graduation_year,
                    "field_of_study": field if field and self._is_present_in_text(field, raw_text) else "",
                })

        sanitized["education"] = clean_edu

        # ------------------------------------------------------------------
        # projects — NuExtract adapter doesn't output projects; default empty
        # ------------------------------------------------------------------
        sanitized["projects"] = []

        # ------------------------------------------------------------------
        # total_experience_years — compute from experience if dates available
        # ------------------------------------------------------------------
        sanitized["total_experience_years"] = self._compute_experience_years(clean_exp)

        # ------------------------------------------------------------------
        # preferred_roles — not in adapter schema; default empty
        # ------------------------------------------------------------------
        sanitized["preferred_roles"] = []

        return sanitized

    # ------------------------------------------------------------------
    # Experience year computation
    # ------------------------------------------------------------------

    def _compute_experience_years(self, experience: List[Dict[str, Any]]) -> Optional[float]:
        """
        Compute total experience in years from parsed experience entries.
        Returns None if reliable dates are not available.
        """
        import datetime
        current_year = datetime.datetime.now().year
        total_months = 0
        calculated = False

        for exp in experience:
            start = exp.get("start_date", "")
            end = exp.get("end_date", "")

            start_year = self._extract_year(start)
            end_year_str = end.strip().lower() if end else ""

            if not start_year:
                continue

            if end_year_str in ("present", "current", "till date", "ongoing", ""):
                end_year = current_year
            else:
                end_year = self._extract_year(end)
                if not end_year:
                    continue

            try:
                months = (int(end_year) - int(start_year)) * 12
                if months > 0:
                    total_months += months
                    calculated = True
            except (TypeError, ValueError):
                pass

        if not calculated:
            return None
        years = round(total_months / 12, 1)
        return years if years > 0 else None

    # ------------------------------------------------------------------
    # Main extraction entry point
    # ------------------------------------------------------------------

    def extract_candidate_profile(self, text: str) -> CandidateProfile:
        """
        Extract structured candidate information from resume text.

        Uses NuExtract with the resume-specific LoRA adapter, then validates
        every extracted value against the original raw text to eliminate
        hallucinations.
        """
        if not text or not text.strip():
            raise ValueError("Resume text is empty. PDF text extraction failed.")

        self.load_model()

        import torch

        schema_json = json.dumps(TEMPLATE_SCHEMA, indent=2)
        clean_text = text.strip()

        prompt = (
            "<|input|>\n"
            f"### Template:\n{schema_json}\n"
            f"### Text:\n{clean_text}\n\n"
            "<|output|>"
        )

        try:
            max_input_tokens = 1024

            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=max_input_tokens,
            )

            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id,
                )

            input_length = inputs["input_ids"].shape[1]
            generated_tokens = outputs[0][input_length:]

            decoded = self.tokenizer.decode(
                generated_tokens,
                skip_special_tokens=True,
            ).strip()

            logger.info("NuExtract raw output: %s", decoded)

            if not decoded:
                raise RuntimeError(
                    "Resume extraction model returned an empty response."
                )

            # Extract JSON block from model output
            json_block = self._extract_first_json(decoded)

            if not json_block:
                raise RuntimeError(
                    f"Resume extraction model did not return JSON. "
                    f"Output: {decoded[:500]}"
                )

            # Parse JSON, repairing truncation if needed
            try:
                raw_data = json.loads(json_block)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON decode failed, attempting truncation repair: %s",
                    json_block[:200],
                )
                repaired = self._repair_truncated_json(json_block)
                try:
                    raw_data = json.loads(repaired)
                    logger.info("JSON repaired successfully.")
                except json.JSONDecodeError:
                    logger.error(
                        "Invalid JSON returned by resume model (even after repair): %s",
                        json_block[:1000],
                    )
                    raise RuntimeError(
                        "Resume extraction model returned invalid JSON."
                    ) from exc

            if not isinstance(raw_data, dict):
                raise RuntimeError(
                    "Resume extraction model returned JSON but it was not an object."
                )

            # Sanitize and ground every field against the original raw text
            sanitized_data = self._sanitize_extracted_data(raw_data, clean_text)

            profile = CandidateProfile(**sanitized_data)

            logger.info(
                "Extraction complete — name=%s, skills=%d, experience=%d, education=%d",
                profile.name,
                len(profile.skills),
                len(profile.experience),
                len(profile.education),
            )

            # Do not allow a completely empty profile
            has_data = any([
                profile.name,
                profile.email,
                profile.phone,
                profile.skills,
                profile.experience,
                profile.education,
            ])

            if not has_data:
                raise RuntimeError(
                    "Resume extraction produced an empty profile. "
                    "The model could not identify any structured information."
                )

            return profile

        except RuntimeError:
            raise

        except Exception as exc:
            logger.exception("Unexpected error during resume extraction")
            raise RuntimeError(
                f"Resume extraction failed: {exc}"
            ) from exc