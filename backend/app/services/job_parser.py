"""
Job requirement parser service.

Uses the NuExtract-tiny model (same infrastructure as resume_extractor.py)
to parse structured job requirements from a Job title and description.

Caches results alongside search data so re-matching doesn't require re-extraction.
"""
import json
import logging
import re
from typing import Optional

from app.models.job import Job
from app.models.job_requirements import JobRequirements

logger = logging.getLogger(__name__)

# Template we ask NuExtract to fill from the job description
_JD_TEMPLATE = {
    "required_skills": [],
    "preferred_skills": [],
    "min_experience_years": "",
    "max_experience_years": "",
    "education_requirements": [],
    "location": "",
    "employment_type": "",
    "extracted_keywords": [],
}


class JobParserService:
    """
    Extracts structured JobRequirements from a Job's title and description
    using the NuExtract-tiny model (loaded once via singleton pattern).
    """

    _instance: Optional["JobParserService"] = None

    def __new__(cls) -> "JobParserService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._tokenizer = None
        return cls._instance

    def load_model(self) -> None:
        """Load model/tokenizer once (reuse from ResumeExtractorService if possible)."""
        if self._model is not None:
            return
        import os
        if os.getenv("TESTING") == "1":
            logger.info("TESTING mode — skipping JobParserService model load.")
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = "nimendraai/NuExtract-tiny-Resume-Data-Extractor"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading JobParserService model '{model_id}' on {device}...")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
            )
            if device == "cpu":
                self._model = self._model.to("cpu")
            logger.info("JobParserService model loaded.")
        except Exception as e:
            logger.error(f"JobParserService model load failed: {e}")
            raise RuntimeError(f"Model loading failed: {e}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_json_block(self, text: str) -> str:
        if "<|output|>" in text:
            part = text.split("<|output|>")[1]
            if "<|end-output|>" in part:
                part = part.split("<|end-output|>")[0]
            elif "<|" in part:
                part = part.split("<|")[0]
            return part.strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        return m.group(0).strip() if m else text.strip()

    def _sanitize(self, data: dict) -> dict:
        """Coerce model outputs into the types JobRequirements expects."""
        result = dict(data)

        # Experience years: "3" / "3-5" / "3 years" -> float | None
        for key in ("min_experience_years", "max_experience_years"):
            raw = result.get(key)
            if raw is not None and raw != "":
                nums = re.findall(r"\d+(?:\.\d+)?", str(raw))
                if nums:
                    result[key] = float(nums[0])
                else:
                    result[key] = None
            else:
                result[key] = None

        # Ensure list fields contain only strings
        for field in ("required_skills", "preferred_skills",
                      "education_requirements", "extracted_keywords"):
            v = result.get(field)
            if not isinstance(v, list):
                result[field] = [str(v)] if v else []
            else:
                result[field] = [str(x) for x in v if x]

        # location / employment_type: string or None
        for field in ("location", "employment_type"):
            v = result.get(field)
            result[field] = str(v).strip() if v and str(v).strip() else None

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_job_requirements(self, job: Job) -> JobRequirements:
        """
        Analyse job title + description and return a validated JobRequirements object.

        If the model is not loaded (TESTING mode) or the description is empty,
        returns a safe default object with empty lists.
        """
        jd_text = f"Job Title: {job.title}\n\n{job.description or ''}".strip()

        if not jd_text or not job.description:
            logger.warning(f"Job {job.id} has no description — returning empty requirements.")
            return JobRequirements(job_id=job.id)

        if self._model is None and os.getenv("TESTING") != "1":
            try:
                self.load_model()
            except Exception as e:
                logger.error(f"Lazy loading of JobParserService failed: {e}")

        if self._model is None:
            logger.warning("JobParserService model not loaded — returning empty requirements.")
            return JobRequirements(job_id=job.id)

        schema_json = json.dumps(_JD_TEMPLATE, indent=2)
        prompt = f"<|input|>\n### Template:\n{schema_json}\n### Text:\n{jd_text}\n\n<|output|>"

        try:
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.0,
                do_sample=False,
            )
            generated = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
            json_block = self._extract_json_block(generated)
            raw = json.loads(json_block)
        except Exception as e:
            logger.error(f"JobParserService inference error for job {job.id}: {e}")
            return JobRequirements(job_id=job.id)

        sanitized = self._sanitize(raw)
        try:
            return JobRequirements(job_id=job.id, **sanitized)
        except Exception as ve:
            logger.error(f"Pydantic validation error for job {job.id}: {ve}")
            return JobRequirements(job_id=job.id)
