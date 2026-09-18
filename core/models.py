"""Typed values exchanged by future GradeAssist pipeline stages."""
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DecisionStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ESCALATED = "escalated"
    COMPLETED = "completed"

class QuestionExtraction(BaseModel):
    question_number: int = Field(gt=0)
    extracted_mark: float | None = Field(default=None, ge=0)
    max_mark: float | None = Field(default=None, gt=0)
    confidence: float = Field(ge=0, le=1)
    raw_text: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)

class ExtractionResult(BaseModel):
    assessment_id: int | None = None
    source_path: str
    questions: list[QuestionExtraction] = Field(default_factory=list)
    confidence_band: ConfidenceBand | None = None
    student_name: str | None = None
    reported_total: float | None = Field(default=None, ge=0)
    requires_review: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class DualReadExtractionResult(BaseModel):
    first_read: ExtractionResult
    second_read: ExtractionResult
    field_agreement: dict[str, float] = Field(default_factory=dict)
    agreement_score: float = Field(ge=0, le=1)

class ConfidenceResult(BaseModel):
    raw_confidence: float = Field(ge=0, le=1)
    dual_read_agreement: float = Field(ge=0, le=1)
    total_cross_check: float = Field(ge=0, le=1)
    name_match_score: float = Field(ge=0, le=1)
    matched_student_id: int | None = None
    checks: dict[str, bool] = Field(default_factory=dict)

class VisionStudent(BaseModel):
    name: str | None = None
    class_name: str | None = Field(default=None, alias="class")
    date: str | None = None
    subject: str | None = None

class TeacherMarkingType(StrEnum):
    TICK = "tick"
    CROSS = "cross"
    WRITTEN_MARK = "written_mark"
    COMMENT = "comment"
    UNCLEAR = "unclear"

class VisionTeacherMarking(BaseModel):
    marking_type: TeacherMarkingType
    visible_text: str | None = None

class VisionQuestion(BaseModel):
    question_number: str | None = None
    question_text: str | None = None
    student_answer: str | None = None
    working_steps: list[str] = Field(default_factory=list)
    teacher_marking: VisionTeacherMarking | None = None
    individual_score: "VisionScore | None" = None
    uncertain_fields: list[str] = Field(default_factory=list)

    @field_validator("question_number", mode="before")
    @classmethod
    def normalize_question_number(cls, value: object) -> str | None:
        return None if value is None else str(value)

    @field_validator("working_steps", mode="before")
    @classmethod
    def normalize_working_steps(cls, value: object) -> list[object]:
        return [] if value is None else value

    @field_validator("student_answer", mode="before")
    @classmethod
    def normalize_student_answer(cls, value: object) -> str | None:
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return "\n".join(value)
        return value

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_mark_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = value.copy()
        legacy_mark = data.pop("teacher_mark", None)
        if legacy_mark is not None and "teacher_marking" not in data:
            text = str(legacy_mark)
            kind = "tick" if text.casefold() in {"tick", "✓"} else "cross" if text.casefold() in {"cross", "x", "✗"} else "written_mark"
            data["teacher_marking"] = {"marking_type": kind, "visible_text": text}
        legacy_score = data.pop("marks_awarded", None)
        if legacy_score is not None and "individual_score" not in data:
            data["individual_score"] = {"obtained": legacy_score, "maximum": None}
        data.pop("confidence", None)
        return data

class VisionScore(BaseModel):
    obtained: float | None = None
    maximum: float | None = None

class VisionSection(BaseModel):
    section_name: str | None = None
    section_score: VisionScore | None = None
    questions: list[VisionQuestion] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)

class VisionExtraction(BaseModel):
    student: VisionStudent = Field(default_factory=VisionStudent)
    sections: list[VisionSection] = Field(default_factory=list)
    score: VisionScore = Field(default_factory=VisionScore)
    teacher_comments: list[str] = Field(default_factory=list)
    uncertain_items: list[str] = Field(default_factory=list)

    @field_validator("teacher_comments", mode="before")
    @classmethod
    def normalize_teacher_comments(cls, value: object) -> list[object]:
        if value is None:
            return []
        return [value] if isinstance(value, str) else value

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_flat_questions(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = value.copy()
        legacy_questions = data.pop("questions", None)
        if legacy_questions and "sections" not in data:
            data["sections"] = [{"section_name": None, "section_score": None, "questions": legacy_questions}]
        return data

    @property
    def questions(self) -> list[VisionQuestion]:
        """Compatibility view for the older dual-read prototype; not part of OCR JSON."""
        return [question for section in self.sections for question in section.questions]

class ScoringResult(BaseModel):
    assessment_id: int
    student_id: int
    total_score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    topic_scores: dict[str, float] = Field(default_factory=dict)

class DecisionResult(BaseModel):
    student_id: int
    assessment_id: int
    status: DecisionStatus = DecisionStatus.PENDING
    recommended_action: str
    rationale: str
    confidence: float = Field(ge=0, le=1)
    requires_teacher_confirmation: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
