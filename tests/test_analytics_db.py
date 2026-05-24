import pytest
from sqlmodel import create_engine, Session, SQLModel
from app.models import User, AssessmentHistory
from datetime import datetime, timedelta

# In-memory SQLite database for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine) # Clean up after tests

def test_store_and_retrieve_assessment_history(session: Session):
    # Create a test user
    user = User(email="test@example.com", hashed_password="hashedpassword")
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create an AssessmentHistory instance
    assessment_time = datetime.utcnow() - timedelta(hours=1)
    assessment = AssessmentHistory(
        user_id=user.id,
        timestamp=assessment_time,
        commute_type="driving",
        commute_distance_km=10.5,
        duration_minutes=20.0,
    )

    # Store the assessment
    session.add(assessment)
    session.commit()
    session.refresh(assessment)

    assert assessment.id is not None
    assert assessment.user_id == user.id

    # Retrieve the assessment
    retrieved_assessment = session.get(AssessmentHistory, assessment.id)

    assert retrieved_assessment is not None
    assert retrieved_assessment.user_id == user.id
    assert retrieved_assessment.timestamp.isoformat() == assessment_time.isoformat() # Compare ISO format due to potential microsecond differences
    assert retrieved_assessment.commute_type == "driving"
    assert retrieved_assessment.commute_distance_km == 10.5
    assert retrieved_assessment.duration_minutes == 20.0
    assert retrieved_assessment.created_at is not None

    # Test relationship
    assert retrieved_assessment.user.email == user.email
