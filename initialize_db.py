"""Initialize GradeAssist's local SQLite schema."""
from database import initialize_database
from database.seed import seed_demo_data

if __name__ == "__main__":
    print(f"Initialized database: {initialize_database()}")
