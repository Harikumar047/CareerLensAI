from transformers.models.encoder_decoder import modeling_encoder_decoder
import json
import logging
import re
from typing import Dict, Any, Optional
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
# Field names follow the adapter's output schema from the model card.
# ---------------------------------------------------------------------------
TEMPLATE_SCHEMA = {
    "name": "",
    "email": "",
    "phone": "",
    "website": "",
    "skills": [""],
    "experience": [{"title": "", "company": "", "duration": ""}],
    "education": [{"degree": "", "institution": "", "year": ""}],
    "other_details": [""],
}


class ResumeExtractorService:
    """
    Loads the NuExtract-tiny-v1.5 base model and applies the
    nimendraai/NuExtract-tiny-Resume-Data-Extractor LoRA adapter via PEFT.

    Architecture:
        Base  : numind/NuExtract-tiny-v1.5  (Qwen2.5-0.5B backbone)
        Adapter: nimendraai/NuExtract-tiny-Resume-Data-Extractor (LoRA, r=32)

    Implemented as a singleton so the model is loaded at most once per process.
    Model loading is lazy — it only happens on the first actual extraction call.
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
        nimendraai LoRA adapter using PEFT.  Idempotent — safe to call
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
            # (it uses the same tokenizer as the base, but the adapter repo
            # also ships a copy so we load from there for consistency)
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
            # Clean up partial state so a retry is possible
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
        Brace-counting extractor — recommended in the model card.
        Returns the first complete JSON object found in text, or the
        full text if no balanced braces are found (fallback).
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
        # Fallback — try regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text.strip()

    # ------------------------------------------------------------------
    # Data sanitization
    # ------------------------------------------------------------------

    def _sanitize_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps the adapter's output schema fields to CandidateProfile fields
        and sanitizes types.

        Adapter schema  →  CandidateProfile field
        ─────────────────────────────────────────
        name            →  name
        email           →  email
        phone           →  phone
        website         →  (ignored, no field in schema)
        skills          →  skills
        experience      →  experience  (title→role, duration stays)
        education       →  education   (year→graduation_year)
        other_details   →  certifications (best fit)
        """
        sanitized: Dict[str, Any] = {}

        # Scalar string fields
        for field in ("name", "email", "phone", "location"):
            sanitized[field] = data.get(field) or None

        # skills — list of strings
        raw_skills = data.get("skills", [])
        if isinstance(raw_skills, list):
            sanitized["skills"] = [str(s).strip() for s in raw_skills if s and str(s).strip()]
        else:
            sanitized["skills"] = [str(raw_skills)] if raw_skills else []

        # other_details → certifications
        raw_other = data.get("other_details", [])
        if isinstance(raw_other, list):
            sanitized["certifications"] = [str(s).strip() for s in raw_other if s and str(s).strip()]
        else:
            sanitized["certifications"] = [str(raw_other)] if raw_other else []

        # experience: adapter uses title/company/duration
        raw_exp = data.get("experience", [])
        clean_exp = []
        if isinstance(raw_exp, list):
            for item in raw_exp:
                if not isinstance(item, dict):
                    continue
                # Map adapter fields → CandidateProfile.Experience fields
                clean_exp.append({
                    "role": item.get("title") or item.get("role") or "",
                    "company": item.get("company") or "",
                    "start_date": item.get("duration") or "",
                    "end_date": "",
                    "description": item.get("description") or "",
                    "skills": [],
                })
        sanitized["experience"] = clean_exp

        # education: adapter uses degree/institution/year
        raw_edu = data.get("education", [])
        clean_edu = []
        if isinstance(raw_edu, list):
            for item in raw_edu:
                if not isinstance(item, dict):
                    continue
                # Parse year to int
                raw_year = item.get("year") or item.get("graduation_year") or ""
                graduation_year = None
                if raw_year:
                    digits = re.findall(r"\d{4}", str(raw_year))
                    if digits:
                        try:
                            graduation_year = int(digits[0])
                        except ValueError:
                            pass
                clean_edu.append({
                    "degree": item.get("degree") or "",
                    "institution": item.get("institution") or "",
                    "graduation_year": graduation_year,
                    "field_of_study": item.get("field_of_study") or "",
                })
        sanitized["education"] = clean_edu

        # projects — not in adapter schema; default to empty
        sanitized["projects"] = []

        # total_experience_years — not in adapter schema; default to None
        sanitized["total_experience_years"] = None

        # preferred_roles — not in adapter schema; default to empty
        sanitized["preferred_roles"] = []

        return sanitized

    # ------------------------------------------------------------------
    # Main extraction entry point
    # ------------------------------------------------------------------

    def extract_candidate_profile(self, text: str) -> CandidateProfile:
        """
        Runs inference on raw resume text and returns a structured
        CandidateProfile.  Loads the model lazily if needed.
        """
        if not text or not text.strip():
            logger.warning("Empty text passed to extract_candidate_profile.")
            return CandidateProfile()

        # Lazy model load
        self.load_model()

        import torch

        # Build prompt in the NuExtract <|input|> format
        schema_json = json.dumps(TEMPLATE_SCHEMA, indent=4)
        prompt = (
            "<|input|>\n"
            f"### Template:\n{schema_json}\n"
            f"### Text:\n{text}\n\n"
            "<|output|>"
        )

        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048,
            ).to(self.model.device)

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                    temperature=1.0,   # must be 1.0 when do_sample=False
                )

            decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            print("\n========== NUREXTRACT DECODED OUTPUT ==========")
            print(decoded)
            print("================================================\n")
            # Extract the output portion that comes after <|output|>
            if "<|output|>" in decoded:
                raw_output = decoded.split("<|output|>")[-1].strip()
            else:
                raw_output = decoded.strip()

            # Use brace-counting extraction as recommended in the model card
            json_block = self._extract_first_json(raw_output)

            try:
                raw_data = json.loads(json_block)
            except json.JSONDecodeError as jde:
                logger.error(
                    "Failed to decode model JSON output: %s — Error: %s",
                    json_block[:200],
                    jde,
                )
                return CandidateProfile()

            sanitized_data = self._sanitize_extracted_data(raw_data)
            return CandidateProfile(**sanitized_data)

        except Exception as e:
            logger.error("Inference error during profile extraction: %s", e)
            raise RuntimeError(f"Inference error: {e}") from e
