from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_PATH = Path(__file__).resolve().parents[1] / "interview_bot.db"
engine = create_engine(
    f"sqlite:///{DATABASE_PATH.as_posix()}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session


def initialize_database(database_engine):
    # create_all does not add columns to existing Phase 1 tables.
    with database_engine.begin() as connection:
        if inspect(connection).has_table("interviews"):
            columns = {column["name"] for column in inspect(connection).get_columns("interviews")}
            if "mode" not in columns:
                connection.execute(text("ALTER TABLE interviews ADD COLUMN mode VARCHAR NOT NULL DEFAULT 'recruiter'"))
            if "interview_plan_json" not in columns:
                connection.execute(text("ALTER TABLE interviews ADD COLUMN interview_plan_json TEXT"))
        upgrades = {
            "interviews": {"final_report_json": "TEXT", "report_generated_at": "DATETIME"},
            "interview_turns": {"turn_type": "VARCHAR NOT NULL DEFAULT 'NORMAL'", "changed_condition": "TEXT", "parent_turn_id": "INTEGER", "teaching_note": "TEXT"},
        }
        for table, additions in upgrades.items():
            if inspect(connection).has_table(table):
                columns = {column["name"] for column in inspect(connection).get_columns(table)}
                for name, definition in additions.items():
                    if name not in columns:
                        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        Base.metadata.create_all(bind=connection)
