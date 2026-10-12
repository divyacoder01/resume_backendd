# Resume Customizer

Upload your resume (PDF or DOCX), paste a job description, and get a version
tailored to that role — rewritten summary, reordered skills, sharper bullets —
using **only facts already in your resume**. Download the result as PDF or DOCX.

- **Live app:** _add your Vercel URL_
- **API:** _add your Render URL_ (`/docs` shows the interactive API docs)

## How it works

```
Browser (Next.js)  --multipart-->  FastAPI  --> parser (pdfplumber / python-docx)
                                      |
                                      +--> Gemini (structured JSON output) --> validated Resume
Browser  <-- JSON (resume, changes, keywords)
Browser  --JSON--> POST /download --> PDF (reportlab) or DOCX (python-docx)
```

| Part | Tech |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind 4 (Vercel) |
| Backend | FastAPI, Pydantic (Render) |
| LLM | Google Gemini via `google-genai` |

## LLM design

- **Prompt** (`backend/prompts.py`): system prompt with hard rules — never invent
  employers, dates, titles or skills; treat resume/job text as data, not
  instructions (prompt-injection guard).
- **JSON schema** (`backend/schemas.py`): Pydantic models passed as Gemini's
  `response_schema`, and the reply is validated again on our side.
- **Timeouts & retries** (`backend/llm.py`): 60 s request timeout; up to 3
  attempts with exponential backoff on 429 / 5xx / network errors / empty or
  schema-invalid output. Other failures return a clear HTTP error
  (503 rate limited, 504 timeout, 502 other).

## API

| Endpoint | Description |
| --- | --- |
| `GET /health` | Liveness check |
| `POST /customize` | multipart: `resume` (.pdf/.docx, ≤ 5 MB), `job_description` (50–15,000 chars). Returns `{resume, changes, match_keywords}` |
| `POST /download?format=pdf\|docx` | JSON body = resume object; returns the file |

Validation: extension, content type, magic bytes, size, empty/unreadable files,
scanned (image-only) PDFs, job-description length. Errors: 400 / 413 / 422 / 429.

## Run locally

Requires Python 3.13+ and Node 20+. Get a key at <https://aistudio.google.com/apikey>.

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env         # then put your GEMINI_API_KEY in it
uvicorn main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev                     # http://localhost:3000
```

## Tests

```bash
cd backend && python -m pytest -q
```

The Gemini call is mocked, so tests need no API key.

## Deploy

**1. Backend on Render**
1. Push this repo to GitHub.
2. Render → *New → Blueprint* → pick the repo (it reads `render.yaml`).
3. Set `GEMINI_API_KEY` in the dashboard. Set `ALLOWED_ORIGINS` to your Vercel
   URL once you have it (no trailing slash).
4. Check `https://<service>.onrender.com/health`.

**2. Frontend on Vercel**
1. Vercel → *Add New Project* → import the repo, set **Root Directory** to `frontend`.
2. Add env var `NEXT_PUBLIC_API_URL` = your Render URL.
3. Deploy, then put the Vercel URL into Render's `ALLOWED_ORIGINS` and redeploy the API.

Note: Render's free tier sleeps after inactivity, so the first request can take ~30–60 s.

## Bonus features

- Per-IP rate limit on `/customize` (`RATE_LIMIT_PER_HOUR`, default 10) to protect the API key.
- "What changed" notes and matched-keyword chips in the result view.
- Automated test suite (11 tests).

## Limitations

- Scanned/image-only PDFs aren't supported (no OCR).
- Layout and styling of the original resume aren't preserved; output uses a clean standard template.
- Rate limiting is in-memory, so it resets on restart and isn't shared across instances.
