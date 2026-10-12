import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import ValidationError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from prompts import SYSTEM_PROMPT, build_user_prompt
from schemas import CustomizeResult

load_dotenv()

logger = logging.getLogger("llm")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
REQUEST_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60")) * 1000
MAX_ATTEMPTS = 3


class LLMError(Exception):
    """Final failure of the model call. `status` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class _BadOutput(Exception):
    """Model returned empty/invalid JSON; worth retrying."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _BadOutput):
        return True
    if isinstance(exc, errors.APIError):
        # 408 timeout, 429 rate limit, 5xx server errors
        return exc.code in (408, 429) or (exc.code is not None and exc.code >= 500)
    # network-level problems and client-side timeouts
    return type(exc).__module__.startswith(("httpx", "httpcore")) or isinstance(
        exc, (TimeoutError, ConnectionError)
    )


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not configured on the server.", status=500)
        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    return _client


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _generate(resume_text: str, job_description: str) -> CustomizeResult:
    response = _get_client().models.generate_content(
        model=MODEL,
        contents=build_user_prompt(resume_text, job_description),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CustomizeResult,
            temperature=0.3,
        ),
    )
    if not response.text:
        raise _BadOutput("Empty response (possibly blocked by safety filters).")
    try:
        return CustomizeResult.model_validate_json(response.text)
    except ValidationError as exc:
        raise _BadOutput(f"Response did not match schema: {exc}") from exc


def customize_resume(resume_text: str, job_description: str) -> CustomizeResult:
    """Call Gemini with structured output, retries and a timeout. Raises LLMError."""
    try:
        return _generate(resume_text, job_description)
    except LLMError:
        raise
    except _BadOutput as exc:
        logger.error("Bad model output after retries: %s", exc)
        raise LLMError("The AI returned an unusable answer. Please try again.") from exc
    except errors.APIError as exc:
        logger.error("Gemini API error: %s", exc)
        if exc.code == 429:
            raise LLMError("The AI service is busy (rate limited). Try again shortly.", 503) from exc
        if exc.code in (401, 403):
            raise LLMError("The server's Gemini API key was rejected.", 500) from exc
        raise LLMError("The AI service failed. Please try again.") from exc
    except Exception as exc:
        logger.error("Gemini call failed: %r", exc)
        raise LLMError("The AI service timed out or is unreachable. Please try again.", 504) from exc
