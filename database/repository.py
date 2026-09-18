"""Reusable read queries for GradeAssist persistence; UI code does not contain SQL."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .db import get_connection


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def get_student(student: int | str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Find a student by numeric id or stable student code."""
    field = "id" if isinstance(student, int) else "student_code"
    with get_connection(db_path) as connection:
        row = connection.execute(f"SELECT * FROM students WHERE {field} = ?", (student,)).fetchone()
    return dict(row) if row else None


def get_roster(db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        return _rows(connection.execute("SELECT id, student_code, full_name FROM students WHERE active = 1 ORDER BY full_name"))


def get_student_history(student_id: int, limit: int | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT gr.student_id, a.id AS assessment_id, a.title, a.assessment_date,
               gr.total_score, gr.max_score, ROUND(100.0 * gr.total_score / gr.max_score, 2) AS percentage,
               gr.is_demo
        FROM grading_records gr JOIN assessments a ON a.id = gr.assessment_id
        WHERE gr.student_id = ? ORDER BY a.assessment_date DESC, a.id DESC
    """
    if limit is not None:
        query += " LIMIT ?"
        params: tuple[Any, ...] = (student_id, limit)
    else:
        params = (student_id,)
    with get_connection(db_path) as connection:
        return _rows(connection.execute(query, params))


def get_recent_tests(limit: int = 5, db_path: Path | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT a.*, COUNT(gr.id) AS grading_record_count
        FROM assessments a LEFT JOIN grading_records gr ON gr.assessment_id = a.id
        GROUP BY a.id ORDER BY a.assessment_date DESC, a.id DESC LIMIT ?
    """
    with get_connection(db_path) as connection:
        return _rows(connection.execute(query, (limit,)))


def get_topic_history(student_id: int, topic: int | str, db_path: Path | None = None) -> list[dict[str, Any]]:
    field = "t.id" if isinstance(topic, int) else "t.name"
    query = f"""
        SELECT sth.student_id, t.id AS topic_id, t.name AS topic_name, a.id AS assessment_id,
               a.title, a.assessment_date, sth.score, sth.max_score,
               ROUND(100.0 * sth.score / sth.max_score, 2) AS percentage, sth.is_demo
        FROM student_topic_history sth
        JOIN topics t ON t.id = sth.topic_id JOIN assessments a ON a.id = sth.assessment_id
        WHERE sth.student_id = ? AND {field} = ? ORDER BY a.assessment_date, a.id
    """
    with get_connection(db_path) as connection:
        return _rows(connection.execute(query, (student_id, topic)))


def get_threshold_history(threshold_name: str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM threshold_history"
    params: tuple[Any, ...] = ()
    if threshold_name:
        query += " WHERE threshold_name = ?"
        params = (threshold_name,)
    query += " ORDER BY changed_at DESC, id DESC"
    with get_connection(db_path) as connection:
        return _rows(connection.execute(query, params))


def get_class_topic_history(topic: int | str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT cth.assessment_id, a.title, a.assessment_date, t.id AS topic_id, t.name AS topic_name,
               cth.average_score, cth.max_score, ROUND(100.0 * cth.average_score / cth.max_score, 2) AS percentage,
               cth.student_count, cth.is_demo
        FROM class_topic_performance_history cth
        JOIN topics t ON t.id = cth.topic_id JOIN assessments a ON a.id = cth.assessment_id
    """
    params: tuple[Any, ...] = ()
    if topic is not None:
        field = "t.id" if isinstance(topic, int) else "t.name"
        query += f" WHERE {field} = ?"
        params = (topic,)
    query += " ORDER BY a.assessment_date, a.id, t.name"
    with get_connection(db_path) as connection:
        return _rows(connection.execute(query, params))
