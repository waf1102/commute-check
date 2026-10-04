from sqlmodel import create_engine, Session, SQLModel
from typing import Generator
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///commute_check.db")

# The connect_args is needed for SQLite to allow multi-threaded access.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    # Additive upgrade for existing SQLite installations; preserve saved commutes.
    from sqlalchemy import inspect, text

    columns = {column["name"] for column in inspect(engine).get_columns("commute")}
    with engine.begin() as connection:
        for name, definition in {
            "origin_name": "VARCHAR NOT NULL DEFAULT 'Home'",
            "timezone": "VARCHAR NOT NULL DEFAULT 'UTC'",
            "notification_time": "VARCHAR",
            "return_notification_time": "VARCHAR",
        }.items():
            if name not in columns:
                connection.execute(
                    text(f"ALTER TABLE commute ADD COLUMN {name} {definition}")
                )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
