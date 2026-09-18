"""Central, environment-driven application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _confidence_env(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    environment: str
    debug: bool
    log_level: str
    escalation_floor: float
    threshold_min_clamp: float
    threshold_max_clamp: float
    auto_approve_threshold: float
    recalibration_tighten_step: float
    recalibration_widen_step: float
    dual_read_agreement_min: float
    name_fuzzy_match_threshold: float
    auto_approve_min_evidence_coverage: float
    project_root: Path
    database_path: Path
    data_dir: Path
    ollama_base_url: str
    ollama_vision_model: str
    ollama_vision_timeout_seconds: int
    ollama_vision_num_predict: int
    ollama_vision_num_ctx: int
    hosted_llm_api_key: str | None
    hosted_llm_base_url: str | None
    hosted_llm_model: str | None
    twilio_account_sid: str | None
    twilio_auth_token: str | None
    twilio_whatsapp_from: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from_email: str | None
    smtp_use_tls: bool

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def cached_frames_dir(self) -> Path:
        return self.data_dir / "cached_frames"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    escalation_floor = _confidence_env("ESCALATION_FLOOR", 0.60)
    threshold_min_clamp = _confidence_env("THRESHOLD_MIN_CLAMP", 0.72)
    threshold_max_clamp = _confidence_env("THRESHOLD_MAX_CLAMP", 0.95)
    if threshold_min_clamp > threshold_max_clamp:
        raise ValueError("THRESHOLD_MIN_CLAMP cannot exceed THRESHOLD_MAX_CLAMP")
    requested_auto_approve = _confidence_env("AUTO_APPROVE_THRESHOLD", 0.85)
    recalibration_tighten_step = _confidence_env("RECALIBRATION_TIGHTEN_STEP", 0.01)
    recalibration_widen_step = _confidence_env("RECALIBRATION_WIDEN_STEP", 0.05)
    dual_read_agreement_min = _confidence_env("DUAL_READ_AGREEMENT_MIN", 0.90)
    name_fuzzy_match_threshold = _confidence_env("NAME_FUZZY_MATCH_THRESHOLD", 0.85)
    return Settings(
        app_name=os.getenv("GRADEASSIST_APP_NAME", "GradeAssist"),
        environment=os.getenv("GRADEASSIST_ENVIRONMENT", "development"),
        debug=_bool_env("GRADEASSIST_DEBUG"),
        log_level=os.getenv("GRADEASSIST_LOG_LEVEL", "INFO").upper(),
        escalation_floor=escalation_floor,
        threshold_min_clamp=threshold_min_clamp,
        threshold_max_clamp=threshold_max_clamp,
        auto_approve_threshold=max(threshold_min_clamp, min(requested_auto_approve, threshold_max_clamp)),
        recalibration_tighten_step=recalibration_tighten_step,
        recalibration_widen_step=recalibration_widen_step,
        dual_read_agreement_min=dual_read_agreement_min,
        name_fuzzy_match_threshold=name_fuzzy_match_threshold,
        auto_approve_min_evidence_coverage=_confidence_env("AUTO_APPROVE_MIN_EVIDENCE_COVERAGE", 1.0),
        project_root=PROJECT_ROOT,
        database_path=_project_path(os.getenv("GRADEASSIST_DATABASE_PATH", "database/gradeassist.db")),
        data_dir=_project_path(os.getenv("GRADEASSIST_DATA_DIR", "data")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_vision_model=os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:4b-instruct"),
        ollama_vision_timeout_seconds=int(os.getenv("OLLAMA_VISION_TIMEOUT_SECONDS", "180")),
        ollama_vision_num_predict=int(os.getenv("OLLAMA_VISION_NUM_PREDICT", "4096")),
        ollama_vision_num_ctx=int(os.getenv("OLLAMA_VISION_NUM_CTX", "8192")),
        hosted_llm_api_key=os.getenv("HOSTED_LLM_API_KEY") or None,
        hosted_llm_base_url=os.getenv("HOSTED_LLM_BASE_URL") or None,
        hosted_llm_model=os.getenv("HOSTED_LLM_MODEL") or None,
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        twilio_whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM") or None,
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from_email=os.getenv("SMTP_FROM_EMAIL") or None,
        smtp_use_tls=_bool_env("SMTP_USE_TLS", True),
    )
