import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database import (get_class_topic_history, get_recent_tests, get_student,
                      get_student_history, get_threshold_history, get_topic_history,
                      initialize_database)
from database.db import get_connection
from database.seed import seed_demo_data


class DatabaseFoundationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "gradeassist-test.db"
        initialize_database(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_initialization_is_idempotent(self):
        initialize_database(self.db_path)
        with closing(get_connection(self.db_path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"students", "grading_records", "extracted_marks", "student_topic_history", "class_topic_performance_history"}.issubset(tables))

    def test_foreign_keys_are_enabled(self):
        with closing(get_connection(self.db_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_schema_supports_batches_and_reasoning_tiers(self):
        with closing(get_connection(self.db_path)) as connection:
            assessment_columns = {row[1] for row in connection.execute("PRAGMA table_info(assessments)")}
            decision_columns = {row[1] for row in connection.execute("PRAGMA table_info(decisions)")}
            escalation_columns = {row[1] for row in connection.execute("PRAGMA table_info(escalations)")}
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("assessment_batches", tables)
        self.assertIn("batch_id", assessment_columns)
        self.assertIn("reasoning_tier", decision_columns)
        self.assertIn("reasoning_tier", escalation_columns)

    def test_demo_seed_is_idempotent(self):
        seed_demo_data(self.db_path)
        seed_demo_data(self.db_path)
        with closing(get_connection(self.db_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM students WHERE is_demo = 1").fetchone()[0], 10)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM assessments WHERE is_demo = 1").fetchone()[0], 4)

    def test_student_and_topic_history_queries(self):
        seed_demo_data(self.db_path)
        aarav = get_student("DEMO-001", self.db_path)
        self.assertEqual(aarav["full_name"], "Aarav Mehta")
        self.assertEqual(len(get_student_history(aarav["id"], db_path=self.db_path)), 4)
        fractions = get_topic_history(aarav["id"], "Fractions", self.db_path)
        self.assertEqual([row["score"] for row in fractions], [5.0, 4.0, 3.0, 2.0])
        self.assertEqual(len(get_recent_tests(db_path=self.db_path)), 4)
        self.assertEqual(len(get_threshold_history(db_path=self.db_path)), 3)

    def test_class_topic_history_shows_declining_fractions_trend(self):
        seed_demo_data(self.db_path)
        class_history = get_class_topic_history("Fractions", self.db_path)
        self.assertEqual(len(class_history), 4)
        self.assertGreater(class_history[0]["percentage"], class_history[-1]["percentage"])


if __name__ == "__main__":
    unittest.main()
