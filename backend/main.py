import os
import time
from collections import defaultdict, deque
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from export import safe_filename, to_docx, to_pdf
from llm import LLMError, customize_resume
from parser import ParseError, extract_text
from schemas import CustomizeResult, Resume

load_dotenv()

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MIN_JD_CHARS = 50
MAX_JD_CHARS = 15_000
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # some browsers send this; extension + magic bytes still checked
}

RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))
_hits: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(request: Request) -> None:
    """Simple in-memory per-IP limit so a public deploy can't drain the Gemini quota."""
    if RATE_LIMIT <= 0:
        return
    forwarded = request.headers.get("x-forwarded-for")  # set by Render's proxy
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, f"Rate limit reached ({RATE_LIMIT} per hour). Try again later.")
    q.append(now)


app = FastAPI(title="Resume Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _validate_file_type(filename: str, content_type: str | None, data: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Unsupported file type. Upload a .pdf or .docx resume.")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unexpected content type: {content_type}")
    # Magic bytes: PDF starts with %PDF, DOCX is a zip (PK)
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a valid PDF.")
    if ext == ".docx" and not data.startswith(b"PK"):
        raise HTTPException(400, "File is not a valid DOCX.")
    return ext


@app.post("/customize", response_model=CustomizeResult)
async def customize(
    request: Request,
    resume: UploadFile = File(...),
    job_description: str = Form(...),
):
    _check_rate_limit(request)
    jd = job_description.strip()
    if len(jd) < MIN_JD_CHARS:
        raise HTTPException(400, f"Job description is too short (min {MIN_JD_CHARS} characters).")
    if len(jd) > MAX_JD_CHARS:
        raise HTTPException(400, f"Job description is too long (max {MAX_JD_CHARS} characters).")

    # Read one byte past the limit so oversized uploads are detected without loading everything.
    data = await resume.read(MAX_FILE_BYTES + 1)
    if not data:
        raise HTTPException(400, "Uploaded resume is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, f"Resume too large (max {MAX_FILE_BYTES // (1024 * 1024)} MB).")

    ext = _validate_file_type(resume.filename, resume.content_type, data)

    try:
        text = extract_text(data, ext)
    except ParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        # Gemini call is blocking; run it off the event loop.
        return await run_in_threadpool(customize_resume, text, jd)
    except LLMError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.post("/download")
def download(resume: Resume, format: Literal["pdf", "docx"] = "pdf"):
    """Turn the (possibly user-edited) tailored resume into a PDF or DOCX file."""
    if format == "pdf":
        content, media = to_pdf(resume), "application/pdf"
    else:
        content = to_docx(resume)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = safe_filename(resume.name, format)
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
