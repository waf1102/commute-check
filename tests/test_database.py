from sqlmodel import SQLModel, create_engine, Session
from app.models import Commute, LegAssessment, RouteAssessmentResult, Status, HourlyWeather
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
    assert "dest_name" in fields
    assert "dest_lat" in fields
    assert "dest_lon" in fields
    assert "return_schedule_time" in fields


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def test_commute_destination_fields(session):
    commute = Commute(
        name="Work Commute",
        lat=37.7749,
        lon=-122.4194,
        dest_name="Office",
        dest_lat=37.3861,
        dest_lon=-122.0839,
        schedule_time="08:00",
        return_schedule_time="17:00",
    )
    session.add(commute)
    session.commit()
    session.refresh(commute)
    assert commute.dest_name == "Office"
    assert commute.dest_lat == 37.3861
    assert commute.dest_lon == -122.0839
    assert commute.return_schedule_time == "17:00"


def test_leg_assessment_and_route_assessment_models():
    weather = HourlyWeather(
        temperature=60.0,
        apparent_temp=58.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    leg = LegAssessment(
        leg_type="outbound",
        location_name="Home",
        schedule_time="08:00",
        status=Status.GO,
        score=100,
        reasons=[],
        weather=weather,
    )
    route_res = RouteAssessmentResult(
        overall_status=Status.GO,
        overall_score=100,
        outbound_leg=leg,
        return_leg=None,
        recommendation="Good to ride",
    )
    assert route_res.overall_status == Status.GO
    assert route_res.outbound_leg.location_name == "Home"
