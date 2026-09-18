"""Small, auditable SQLite connection and initialization helpers."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)


class ManagedConnection(sqlite3.Connection):
    """SQLite context manager that commits/rolls back and closes on exit."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, factory=ManagedConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize_database(db_path: Path | None = None) -> Path:
    path = db_path or get_settings().database_path
    schema_path = get_settings().project_root / "database" / "schema.sql"
    connection = get_connection(path)
    try:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _apply_compatibility_migrations(connection)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_assessments_batch ON assessments(batch_id)")
        connection.commit()
    finally:
        connection.close()
    logger.info("SQLite schema initialized at %s", path)
    return path


def _apply_compatibility_migrations(connection: sqlite3.Connection) -> None:
    """Add demo-identification fields to Segment 1 tables without data loss."""
    required_columns = {
        "students": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "assessments": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "topics": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "assessment_questions": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "question_marks": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "student_history": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "decisions": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "escalations": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "teacher_outcomes": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "threshold_history": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "notifications": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
        "class_topic_trends": "is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1))",
    }
    additional_columns = [
        ("assessments", "batch_id INTEGER REFERENCES assessment_batches(id) ON DELETE SET NULL"),
        ("decisions", "reasoning_tier TEXT NOT NULL DEFAULT 'not_applicable'"),
        ("escalations", "reasoning_tier TEXT NOT NULL DEFAULT 'not_applicable'"),
        ("grading_records", "reported_total_score REAL"),
        ("grading_records", "reported_max_score REAL"),
        ("grading_records", "source_reference TEXT"),
        ("grading_records", "extraction_payload_json TEXT"),
        ("grading_records", "extracted_student_name TEXT"),
        ("grading_records", "teacher_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(teacher_confirmed IN (0, 1))"),
        ("extracted_marks", "extraction_section_id INTEGER REFERENCES extraction_sections(id) ON DELETE SET NULL"),
        ("extracted_marks", "source_question_key TEXT"),
        ("extracted_marks", "source_question_number TEXT"),
        ("extracted_marks", "evidence_json TEXT"),
        ("extracted_marks", "teacher_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(teacher_confirmed IN (0, 1))"),
        ("confidence_evaluations", "evidence_coverage REAL NOT NULL DEFAULT 0 CHECK(evidence_coverage BETWEEN 0 AND 1)"),
    ]
    for table, definition in [*required_columns.items(), *additional_columns]:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        column_name = definition.split()[0]
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
