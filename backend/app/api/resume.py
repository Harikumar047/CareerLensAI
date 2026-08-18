import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from app.config import settings
from app.services.pdf_parser import PDFParser
from app.services.resume_extractor import ResumeExtractorService
from app.models.resume import CandidateProfile

router = APIRouter(prefix="/resume", tags=["resume"])
pdf_parser = PDFParser()
extractor_service = ResumeExtractorService()

class ExtractionSummary(BaseModel):
    skills_found: int = Field(..., description="Number of skills found")
    projects_found: int = Field(..., description="Number of projects found")
    experience_entries: int = Field(..., description="Number of experience entries found")
    education_entries: int = Field(..., description="Number of education entries found")

class ResumeUploadResponse(BaseModel):
    resume_id: str
    profile: CandidateProfile
    extraction_summary: ExtractionSummary

@router.post("/upload", response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile = File(...)) -> ResumeUploadResponse:
    """
    Upload a resume PDF, parse text, extract structured profile, and store both JSON and raw text.
    """
    # 1. Mime-Type and extension check
    if file.content_type != "application/pdf" and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read upload file contents: {str(e)}"
        )

    # 2. Extract raw text from PDF
    parsed_pdf = pdf_parser.parse_pdf(file_bytes, file.filename)
    raw_text = parsed_pdf["extracted_text"]

    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF contains no extractable text."
        )

    # 3. Extract candidate profile using Hugging Face model
    try:
        profile = extractor_service.extract_candidate_profile(raw_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract structured data from resume: {str(e)}"
        )

    # 4. Generate unique ID and persist files
    resume_id = str(uuid.uuid4())
    
    # Save the original PDF
    pdf_path = settings.RESUMES_DIR / f"{resume_id}.pdf"
    try:
        with open(pdf_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save PDF locally: {str(e)}"
        )

    # Save raw text
    txt_path = settings.RESUMES_DIR / f"{resume_id}.txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save raw text locally: {str(e)}"
        )

    # Save structured JSON profile
    json_path = settings.RESUMES_DIR / f"{resume_id}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(profile.model_dump_json(indent=2))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save profile JSON locally: {str(e)}"
        )

    # 5. Build summary and response
    summary = ExtractionSummary(
        skills_found=len(profile.skills),
        projects_found=len(profile.projects),
        experience_entries=len(profile.experience),
        education_entries=len(profile.education)
    )

    return ResumeUploadResponse(
        resume_id=resume_id,
        profile=profile,
        extraction_summary=summary
    )

@router.get("/{resume_id}", response_model=CandidateProfile)
async def get_resume_profile(resume_id: str) -> CandidateProfile:
    """
    Retrieve the structured CandidateProfile JSON for a given resume_id.
    """
    json_path = settings.RESUMES_DIR / f"{resume_id}.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume profile with ID '{resume_id}' not found."
        )

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()
        return CandidateProfile.model_validate_json(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read or parse stored profile: {str(e)}"
        )

@router.get("/{resume_id}/raw-text", response_class=PlainTextResponse)
async def get_resume_raw_text(resume_id: str) -> str:
    """
    Retrieve the raw text for a given resume_id.
    """
    txt_path = settings.RESUMES_DIR / f"{resume_id}.txt"
    if not txt_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Raw text for resume with ID '{resume_id}' not found."
        )

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read stored raw text: {str(e)}"
        )
