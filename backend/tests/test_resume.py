import os
import uuid
import json
import fitz
import pytest
from unittest.mock import patch
from fastapi import status
from app.config import settings
from app.models.resume import CandidateProfile, Education, Experience, Project
from app.services.resume_extractor import ResumeExtractorService

# Helper to generate a valid PDF dynamically
def generate_valid_pdf_bytes(text: str = "Test resume content") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

# Mocked profile returned by default for successful extraction tests
MOCK_PROFILE = CandidateProfile(
    name="Jane Doe",
    email="jane.doe@example.com",
    phone="123-456-7890",
    location="San Francisco, CA",
    skills=["Python", "FastAPI", "Docker"],
    education=[
        Education(
            degree="B.S. Computer Science",
            institution="Stanford University",
            graduation_year=2022,
            field_of_study="Computer Science"
        )
    ],
    experience=[
        Experience(
            company="Tech Corp",
            role="Software Engineer",
            start_date="2022-06",
            end_date="Present",
            description="Developing backend microservices.",
            skills=["Python", "FastAPI"]
        )
    ],
    projects=[
        Project(
            name="Portfolio Website",
            description="Personal portfolio highlighting project works.",
            technologies=["HTML", "CSS", "Python"]
        )
    ],
    certifications=["AWS Certified Developer"],
    total_experience_years=2.0,
    preferred_roles=["Backend Engineer", "Software Engineer"]
)

# ----------------- Schema & Validation Tests -----------------

def test_candidate_profile_validation():
    """
    Test that CandidateProfile parses correctly and tolerates missing information.
    """
    # Empty profile creation should be fully allowed
    profile = CandidateProfile()
    assert profile.name is None
    assert profile.skills == []
    assert profile.education == []

    # Valid instantiation
    assert MOCK_PROFILE.name == "Jane Doe"
    assert MOCK_PROFILE.skills == ["Python", "FastAPI", "Docker"]
    assert MOCK_PROFILE.education[0].graduation_year == 2022


def test_resume_extractor_sanitization():
    """
    Test that ResumeExtractorService correctly maps the adapter's output schema
    (name/email/phone/skills/experience/education/other_details) to CandidateProfile.
    """
    service = ResumeExtractorService()

    # Adapter output uses 'year' (not 'graduation_year') and
    # 'title'/'duration' (not 'role'/'start_date') for experience.
    adapter_output = {
        "name": "John Smith",
        "email": "john@example.com",
        "phone": "999-888-7777",
        "website": "https://johnsmith.dev",
        "skills": ["Python", "Docker"],
        "experience": [
            {"title": "Backend Engineer", "company": "Acme Corp", "duration": "2021 - 2023"}
        ],
        "education": [
            {"degree": "B.Tech CS", "institution": "IIT Delhi", "year": "2021"}
        ],
        "other_details": ["AWS Certified", "Google Cloud Badge"],
    }

    sanitized = service._sanitize_extracted_data(adapter_output)

    # Skills mapped correctly
    assert sanitized["skills"] == ["Python", "Docker"]

    # other_details → certifications
    assert sanitized["certifications"] == ["AWS Certified", "Google Cloud Badge"]

    # Experience: title → role
    assert len(sanitized["experience"]) == 1
    assert sanitized["experience"][0]["role"] == "Backend Engineer"
    assert sanitized["experience"][0]["company"] == "Acme Corp"
    assert sanitized["experience"][0]["start_date"] == "2021 - 2023"

    # Education: year → graduation_year (parsed to int)
    assert len(sanitized["education"]) == 1
    assert sanitized["education"][0]["graduation_year"] == 2021
    assert sanitized["education"][0]["degree"] == "B.Tech CS"

    # Fields not in adapter schema default correctly
    assert sanitized["projects"] == []
    assert sanitized["total_experience_years"] is None


def test_resume_extractor_sanitization_dirty_year():
    """
    Graduation years with surrounding text (e.g. '2019 (Expected)') are parsed
    to the first 4-digit integer found.
    """
    service = ResumeExtractorService()
    adapter_output = {
        "education": [
            {"degree": "BS", "institution": "MIT", "year": "2019 (Expected)"}
        ],
    }
    sanitized = service._sanitize_extracted_data(adapter_output)
    assert sanitized["education"][0]["graduation_year"] == 2019


def test_resume_extractor_sanitization_string_skills():
    """
    Skills sent as a bare string instead of a list are wrapped in a list.
    """
    service = ResumeExtractorService()
    adapter_output = {"skills": "Python, Go"}
    sanitized = service._sanitize_extracted_data(adapter_output)
    # A bare string is treated as a single skill token
    assert sanitized["skills"] == ["Python, Go"]


# ----------------- Endpoint API Tests -----------------

@patch.object(ResumeExtractorService, "extract_candidate_profile", return_value=MOCK_PROFILE)
def test_upload_valid_resume_pdf(mock_extract, client):
    """
    Test uploading a valid PDF resume and checking response fields.
    """
    filename = "test_resume.pdf"
    pdf_bytes = generate_valid_pdf_bytes("Jane Doe\nPython Developer")
    
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    response = client.post("/api/resume/upload", files=files)
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    assert "resume_id" in data
    assert data["profile"]["name"] == "Jane Doe"
    assert data["profile"]["skills"] == ["Python", "FastAPI", "Docker"]
    assert data["extraction_summary"]["skills_found"] == 3
    assert data["extraction_summary"]["projects_found"] == 1
    
    # Check that files were stored
    resume_id = data["resume_id"]
    json_path = settings.RESUMES_DIR / f"{resume_id}.json"
    txt_path = settings.RESUMES_DIR / f"{resume_id}.txt"
    pdf_path = settings.RESUMES_DIR / f"{resume_id}.pdf"
    
    assert json_path.exists()
    assert txt_path.exists()
    assert pdf_path.exists()
    
    # Cleanup
    json_path.unlink()
    txt_path.unlink()
    pdf_path.unlink()


def test_upload_invalid_mime_type(client):
    """
    Test uploading a file with an invalid mime-type (non-PDF).
    """
    files = {"file": ("test.txt", b"plain text", "text/plain")}
    response = client.post("/api/resume/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Only PDF files are supported" in response.json()["detail"]


def test_upload_invalid_pdf_content(client):
    """
    Test uploading a file named as .pdf but containing invalid/corrupt content.
    """
    corrupt_bytes = b"%PDF-1.4\ncorrupted content"
    files = {"file": ("corrupt.pdf", corrupt_bytes, "application/pdf")}
    response = client.post("/api/resume/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Could not open or parse the PDF" in response.json()["detail"]


def test_upload_missing_signature(client):
    """
    Test uploading a file that has .pdf extension but lacks the PDF magic signature.
    """
    bad_bytes = b"Not a PDF file at all"
    files = {"file": ("fake.pdf", bad_bytes, "application/pdf")}
    response = client.post("/api/resume/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid magic signature" in response.json()["detail"]


@patch.object(ResumeExtractorService, "extract_candidate_profile", return_value=MOCK_PROFILE)
def test_get_resume_endpoints(mock_extract, client):
    """
    Test retrieving stored CandidateProfile and raw-text using GET endpoints.
    """
    # 1. Perform upload to generate files
    filename = "test_resume.pdf"
    pdf_bytes = generate_valid_pdf_bytes("Jane Doe\nPython Developer")
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    upload_res = client.post("/api/resume/upload", files=files)
    
    resume_id = upload_res.json()["resume_id"]
    
    # 2. Get Profile JSON
    response_get = client.get(f"/api/resume/{resume_id}")
    assert response_get.status_code == status.HTTP_200_OK
    profile_data = response_get.json()
    assert profile_data["name"] == "Jane Doe"
    
    # 3. Get Raw Text
    response_txt = client.get(f"/api/resume/{resume_id}/raw-text")
    assert response_txt.status_code == status.HTTP_200_OK
    assert "Jane Doe" in response_txt.text
    
    # 4. Cleanup
    (settings.RESUMES_DIR / f"{resume_id}.json").unlink()
    (settings.RESUMES_DIR / f"{resume_id}.txt").unlink()
    (settings.RESUMES_DIR / f"{resume_id}.pdf").unlink()


def test_get_resume_not_found(client):
    """
    Test GET requesting non-existent IDs.
    """
    fake_id = str(uuid.uuid4())
    res_get = client.get(f"/api/resume/{fake_id}")
    assert res_get.status_code == status.HTTP_404_NOT_FOUND

    res_txt = client.get(f"/api/resume/{fake_id}/raw-text")
    assert res_txt.status_code == status.HTTP_404_NOT_FOUND


# --------------------------------------------------------------------------
# Model-loading architecture tests (no real download required)
# --------------------------------------------------------------------------

def test_resume_extractor_model_ids():
    """
    Verify the correct base model and adapter model identifiers are configured
    in the service.  These are the source of truth for the loading architecture.
    """
    from app.services.resume_extractor import BASE_MODEL_ID, ADAPTER_MODEL_ID

    assert BASE_MODEL_ID == "numind/NuExtract-tiny-v1.5", (
        "Base model must be NuExtract-tiny-v1.5 (Qwen2.5-0.5B backbone)"
    )
    assert ADAPTER_MODEL_ID == "nimendraai/NuExtract-tiny-Resume-Data-Extractor", (
        "Adapter must be the nimendraai LoRA fine-tune"
    )


def test_resume_extractor_load_model_uses_peft(monkeypatch):
    """
    Verify that load_model() calls PeftModel.from_pretrained, confirming the
    LoRA adapter path is exercised — without downloading any real models.
    """
    import unittest.mock as mock
    from app.services.resume_extractor import ResumeExtractorService

    # Reset singleton so we can test load path cleanly
    service = ResumeExtractorService.__new__(ResumeExtractorService)
    service._initialized = False
    service.__init__()

    fake_base_model = mock.MagicMock()
    fake_base_model.to.return_value = fake_base_model
    fake_base_model.device = "cpu"
    fake_peft_model = mock.MagicMock()
    fake_peft_model.device = "cpu"
    fake_tokenizer = mock.MagicMock()

    with mock.patch("app.services.resume_extractor.AutoModelForCausalLM") as MockModel, \
         mock.patch("app.services.resume_extractor.AutoTokenizer") as MockTok, \
         mock.patch("app.services.resume_extractor.PeftModel") as MockPeft, \
         mock.patch("app.services.resume_extractor.torch") as MockTorch:

        MockTorch.cuda.is_available.return_value = False
        MockTorch.float32 = float
        MockModel.from_pretrained.return_value = fake_base_model
        MockTok.from_pretrained.return_value = fake_tokenizer
        MockPeft.from_pretrained.return_value = fake_peft_model

        service.load_model()

        # 1. Base model loaded with correct ID
        MockModel.from_pretrained.assert_called_once()
        base_call_args = MockModel.from_pretrained.call_args
        assert base_call_args[0][0] == "numind/NuExtract-tiny-v1.5"

        # 2. Tokenizer loaded from adapter repo
        MockTok.from_pretrained.assert_called_once_with(
            "nimendraai/NuExtract-tiny-Resume-Data-Extractor",
            trust_remote_code=True,
        )

        # 3. PeftModel.from_pretrained called with base model + adapter ID
        MockPeft.from_pretrained.assert_called_once_with(
            fake_base_model,
            "nimendraai/NuExtract-tiny-Resume-Data-Extractor",
        )


def test_resume_extractor_json_brace_counting():
    """
    The brace-counting extractor should correctly isolate the first complete
    JSON object even when trailing text follows it (a known model quirk).
    """
    service = ResumeExtractorService()

    raw = '{"name": "Alice", "skills": ["Python"]} some trailing garbage'
    result = service._extract_first_json(raw)
    assert result == '{"name": "Alice", "skills": ["Python"]}'

    # Nested braces
    nested = '{"a": {"b": 1}} extra'
    assert service._extract_first_json(nested) == '{"a": {"b": 1}}'

    # No braces — returns original
    no_json = "just plain text"
    assert service._extract_first_json(no_json) == "just plain text"
