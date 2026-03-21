from sqlmodel import SQLModel, create_engine
from app.models import Commute
from app import database
import pytest

def test_create_db_and_tables():
    # This is an in-memory SQLite database for testing
    test_engine = create_engine("sqlite:///:memory:")
    
    # We need to create a new engine for testing, not use the global one
    original_engine = database.engine
    database.engine = test_engine

    try:
        # The function to be tested
        database.create_db_and_tables()

        # Check that the table was created
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        assert "commute" in inspector.get_table_names()
    finally:
        database.engine = original_engine

def test_commute_model():
    # Check that the model has the correct fields
    # This is more of a static check, but useful for ensuring the model is correct
    fields = Commute.model_fields
    assert "id" in fields
    assert "name" in fields
    assert "lat" in fields
    assert "lon" in fields
    assert "webhook_url" in fields
    assert "schedule_time" in fields
    assert "max_wind_no_go" in fields
    assert "rain_threshold" in fields
    assert "min_temp_no_go" in fields
