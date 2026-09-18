"""Local Ollama worksheet Vision/OCR service with safe response parsing."""
from __future__ import annotations
import base64, json, re
from pathlib import Path
from typing import Any
import requests
from pydantic import ValidationError
from config import get_settings
from core.logger import get_logger
from core.models import VisionExtraction

logger = get_logger(__name__)
SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
VISION_SCHEMA = VisionExtraction.model_json_schema(by_alias=True)
VISION_PROMPT = """Perform visual extraction only. Extract only visibly supported facts. Identify sections and every assessable subquestion; never collapse multiple visible problems. Preserve student answers exactly, including wrong answers. Distinguish student writing, individual teacher markings, and section scores. Never solve, grade, calculate, or infer correctness. Use null or uncertain_fields when unreadable and [] when no working steps are visible. Return JSON only matching the supplied schema; no prose, reasoning, or model confidence."""

class VisionServiceError(RuntimeError):
    def __init__(self, message: str, raw_response: str | None = None, metadata: dict[str, Any] | None = None):
        super().__init__(message); self.raw_response = raw_response; self.metadata = metadata or {}
class UnsupportedImageTypeError(VisionServiceError): pass
class ImageNotFoundError(VisionServiceError): pass
class VisionOllamaConnectionError(VisionServiceError): pass
class VisionOllamaTimeoutError(VisionServiceError): pass
class OllamaModelError(VisionServiceError): pass
class VisionEmptyResponseError(VisionServiceError): pass
class VisionJSONExtractionError(VisionServiceError): pass
class VisionJSONDecodeError(VisionServiceError): pass
class VisionSchemaValidationError(VisionServiceError): pass
class VisionTruncatedResponseError(VisionServiceError): pass
# Backwards-compatible alias for the first Vision/OCR test boundary.
MalformedVisionResponseError = VisionJSONDecodeError
OllamaUnavailableError = VisionOllamaConnectionError
OllamaTimeoutError = VisionOllamaTimeoutError

def _validate_image(path: str | Path) -> Path:
    image = Path(path)
    if not image.is_file(): raise ImageNotFoundError(f"Image file not found: {image}")
    if image.suffix.lower() not in SUPPORTED_IMAGE_TYPES: raise UnsupportedImageTypeError(f"Unsupported image type '{image.suffix}'. Use: {', '.join(sorted(SUPPORTED_IMAGE_TYPES))}")
    return image

def _generation_metadata(envelope: dict[str, Any], content: str, configured_num_predict: int, configured_num_ctx: int, model: str) -> dict[str, Any]:
    eval_count = envelope.get("eval_count")
    return {"done": envelope.get("done"), "done_reason": envelope.get("done_reason"), "eval_count": eval_count, "eval_duration": envelope.get("eval_duration"), "prompt_eval_count": envelope.get("prompt_eval_count"), "prompt_eval_duration": envelope.get("prompt_eval_duration"), "total_duration": envelope.get("total_duration"), "load_duration": envelope.get("load_duration"), "configured_num_predict": configured_num_predict, "configured_num_ctx": configured_num_ctx, "model": model, "response_text_length": len(content), "eval_count_reached_limit": isinstance(eval_count, int) and eval_count >= configured_num_predict, "response_ends_mid_json": bool(content.strip()) and not content.rstrip().endswith("}")}

def _extract_json_text(content: str) -> str:
    text = content.strip()
    if not text: raise VisionEmptyResponseError("Ollama returned an empty model response", content)
    fenced = list(re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE))
    if len(fenced) > 1: raise VisionJSONExtractionError("Ollama response contains multiple fenced JSON candidates", content)
    if len(fenced) == 1:
        if "{" in text[fenced[0].end():]: raise VisionJSONExtractionError("Ollama response has multiple JSON objects", content)
        return fenced[0].group(1).strip()
    decoder = json.JSONDecoder()
    candidates: list[tuple[object, int, int]] = []
    for index, char in enumerate(text):
        if char != "{": continue
        try:
            parsed, end = decoder.raw_decode(text[index:])
            candidates.append((parsed, index, index + end))
        except json.JSONDecodeError: continue
    if not candidates:
        if "{" in text:
            candidate = text[text.index("{"):]
            if not candidate.rstrip().endswith("}"):
                raise VisionTruncatedResponseError("Ollama response appears truncated or incomplete", content)
            try: json.loads(candidate)
            except json.JSONDecodeError as error: raise VisionJSONDecodeError(f"Ollama returned invalid JSON: {error.msg}", content) from error
        if text.lstrip().startswith("{"):
            raise VisionTruncatedResponseError("Ollama response appears truncated or incomplete", content)
        raise VisionJSONExtractionError("No complete JSON object found in Ollama response", content)
    outer = [candidate for candidate in candidates if not any(other[1] < candidate[1] < other[2] for other in candidates)]
    if len(outer) != 1: raise VisionJSONExtractionError("Ollama response has ambiguous JSON objects", content)
    _, start, end = outer[0]
    if "{" in text[end:]: raise VisionJSONExtractionError("Ollama response has multiple JSON objects", content)
    return text[start:end]

# Compatibility name used by earlier tests; extraction now handles prose too.
_clean_json = _extract_json_text

def _parse_extraction(content: str) -> VisionExtraction:
    candidate = _extract_json_text(content)
    try: payload = json.loads(candidate)
    except json.JSONDecodeError as error:
        if error.pos >= len(candidate) - 2 or not candidate.rstrip().endswith("}"): raise VisionTruncatedResponseError("Ollama response appears truncated or incomplete", content) from error
        raise VisionJSONDecodeError(f"Ollama returned invalid JSON: {error.msg}", content) from error
    if not isinstance(payload, dict): raise VisionJSONExtractionError("Ollama JSON extraction must be an object", content)
    try: return VisionExtraction.model_validate(payload)
    except ValidationError as error: raise VisionSchemaValidationError(f"Ollama JSON does not match VisionExtraction: {error.errors(include_url=False)}", content) from error

class OllamaVisionService:
    def __init__(self, base_url: str | None = None, model: str | None = None, session: Any = requests, timeout: int | None = None):
        settings = get_settings(); self.settings = settings
        self.base_url, self.model, self.session, self.timeout = (base_url or settings.ollama_base_url).rstrip("/"), model or settings.ollama_vision_model, session, timeout or settings.ollama_vision_timeout_seconds

    def extract(self, image_path: str | Path) -> VisionExtraction:
        image = _validate_image(image_path)
        image_b64 = base64.b64encode(image.read_bytes()).decode("ascii")
        logger.info("Sending worksheet image '%s' to local Ollama model '%s'", image.name, self.model)
        try: response = self.session.post(f"{self.base_url}/api/generate", json={"model": self.model, "prompt": VISION_PROMPT, "images": [image_b64], "stream": False, "format": VISION_SCHEMA, "options": {"num_predict": self.settings.ollama_vision_num_predict, "num_ctx": self.settings.ollama_vision_num_ctx}}, timeout=self.timeout)
        except requests.Timeout as error: raise VisionOllamaTimeoutError("Ollama vision request timed out") from error
        except requests.ConnectionError as error: raise VisionOllamaConnectionError(f"Ollama is unavailable at {self.base_url}") from error
        except requests.RequestException as error: raise VisionOllamaConnectionError(f"Ollama request failed: {error}") from error
        if response.status_code == 404: raise OllamaModelError(f"Ollama model '{self.model}' is unavailable")
        try: response.raise_for_status(); envelope = response.json(); content = envelope.get("response")
        except (requests.RequestException, ValueError, AttributeError) as error: raise VisionOllamaConnectionError("Ollama returned an invalid API envelope") from error
        if not isinstance(content, str) or not content.strip(): raise VisionEmptyResponseError("Ollama returned an empty model response")
        metadata = _generation_metadata(envelope, content, self.settings.ollama_vision_num_predict, self.settings.ollama_vision_num_ctx, self.model)
        if self.settings.debug: logger.debug("Vision generation metadata=%s", metadata)
        if envelope.get("done") is False or envelope.get("done_reason") == "length":
            raise VisionTruncatedResponseError(f"Ollama stopped before completing its response (done_reason={metadata['done_reason']}, eval_count={metadata['eval_count']}, num_predict={metadata['configured_num_predict']})", content, metadata)
        try: return _parse_extraction(content)
        except VisionServiceError as error:
            if self.settings.debug: logger.debug("Vision parsing failure metadata=%s raw_response=%r", error.metadata, error.raw_response or content)
            raise

def extract_worksheet(image_path: str | Path) -> VisionExtraction: return OllamaVisionService().extract(image_path)

def extract_mark_read(image_path: str | Path) -> dict[str, Any]:
    extraction = extract_worksheet(image_path)
    return {"student_name": extraction.student.name, "reported_total": extraction.score.obtained, "questions": []}
