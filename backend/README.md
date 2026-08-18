# CareerLensAI Backend

CareerLensAI is an AI-powered career mentor for students. This repository contains the backend service built with FastAPI.

## Folder Tree

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── resume.py
│   │   ├── jobs.py
│   │   ├── matching.py
│   │   └── mentor.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── resume.py
│   │   ├── job.py
│   │   └── matching.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py
│   │   ├── resume_extractor.py
│   │   ├── job_client.py
│   │   ├── job_parser.py
│   │   ├── matcher.py
│   │   ├── course_recommender.py
│   │   └── mentor.py
│   │
│   └── data/
│       ├── resumes/
│       ├── jobs/
│       └── courses/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_main.py
│   ├── test_resume.py
│   └── test_jobs.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Setup & Installation

### 1. Create Virtual Environment

Navigate to the `backend` folder and run:

```bash
# Windows
python -m venv .venv

# macOS / Linux
python3 -m venv .venv
```

### 2. Activate Virtual Environment

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create local `.env`

Copy the template:

```bash
cp .env.example .env
```

And update it with your credentials:
```env
ADZUNA_APP_ID=your_registered_adzuna_app_id
ADZUNA_APP_KEY=your_registered_adzuna_app_key
ADZUNA_COUNTRY=in
```

---

## Running the Server

Start the local development server:

```bash
uvicorn app.main:app --reload
```

By default, the server starts at `http://127.0.0.1:8000`. You can view the interactive documentation at `http://127.0.0.1:8000/docs`.

---

## Running Tests

To run the test suite:

```bash
pytest
```

---

## API & Curl Examples

### Health Check

```bash
curl -X GET http://127.0.0.1:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "app_name": "CareerLensAI Backend"
}
```

### Resume PDF Upload

Upload a PDF resume:

```bash
curl -X POST http://127.0.0.1:8000/api/resume/upload \
  -H "Accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/resume.pdf"
```

**Response:**
```json
{
  "resume_id": "78096f2a-e24c-47bc-ad85-dfa52f9c9dfd",
  "profile": {
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "123-456-7890",
    "location": "Chennai",
    "skills": ["Python", "FastAPI"],
    "education": [],
    "experience": [],
    "projects": [],
    "certifications": [],
    "total_experience_years": null,
    "preferred_roles": []
  },
  "extraction_summary": {
    "skills_found": 2,
    "projects_found": 0,
    "experience_entries": 0,
    "education_entries": 0
  }
}
```

### Live Job Search

Search jobs matching queries:

```bash
curl -X GET "http://127.0.0.1:8000/api/jobs/search?role=software%20developer&location=Chennai"
```

**Response:**
```json
{
  "query": {
    "role": "software developer",
    "location": "Chennai",
    "page": 1,
    "results_per_page": 20,
    "max_days_old": null
  },
  "total_returned": 1,
  "jobs": [
    {
      "id": "adzuna_12345678",
      "source": "adzuna",
      "title": "Software Developer",
      "company": "Example Solutions",
      "location": "Chennai, Tamil Nadu",
      "description": "Develop backends in Python and FastAPI...",
      "salary_min": 600000.0,
      "salary_max": 800000.0,
      "contract_type": "permanent",
      "contract_time": "full_time",
      "category": "IT Jobs",
      "created": "2026-08-17T12:00:00Z",
      "url": "https://example.com/redirect"
    }
  ],
  "retrieved_at": "2026-08-17T17:02:00.123456Z"
}
```
Each search is saved under `app/data/jobs/search_<uuid>.json` for tracking purposes.
