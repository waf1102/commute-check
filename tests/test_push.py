import pytest
from sqlmodel import Session, SQLModel, create_engine
from app.models import User
from app.push.models import PushSubscription
from app.push.vapid import get_or_create_vapid_keys

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_push.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

def test_vapid_key_generation():
    private_key, public_key = get_or_create_vapid_keys()
    assert private_key is not None
    assert public_key is not None
    assert len(public_key) > 20

def test_push_subscription_model(session: Session):
    user = User(email="pushuser@example.com", hashed_password="hashed_pw")
    session.add(user)
    session.commit()
    session.refresh(user)

    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/test_token",
        p256dh="test_p256dh",
        auth="test_auth",
        user_agent="Mozilla/5.0"
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    assert sub.id is not None
    assert sub.user_id == user.id
    assert sub.endpoint == "https://fcm.googleapis.com/fcm/send/test_token"
