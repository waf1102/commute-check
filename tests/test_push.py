import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from py_vapid import Vapid
from datetime import datetime, timedelta, timezone
from jose import jwt
from pywebpush import WebPushException

from app.main import app
from app.database import get_session
from app.models import User
from app.push.models import PushSubscription
from app.push.vapid import get_or_create_vapid_keys
import os
from app.security import ALGORITHM, SECRET_KEY, get_password_hash

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_push.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)


@pytest.fixture(autouse=True, scope="module")
def cleanup_test_db():
    yield
    engine.dispose()
    if os.path.exists("./test_push.db"):
        try:
            os.remove("./test_push.db")
        except OSError:
            pass


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


@pytest.fixture(name="session")
def session_fixture():
    create_db_and_tables()
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def create_test_user(
    session: Session,
    email: str = "pushuser@example.com",
    password: str = "testpassword",
) -> User:
    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_auth_token(email: str = "pushuser@example.com") -> str:
    access_token_expires = timedelta(minutes=30)
    to_encode = {"sub": email}
    expire = datetime.now(timezone.utc) + access_token_expires
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@pytest.fixture
def auth_headers(session: Session):
    user = create_test_user(session)
    token = get_auth_token(email=user.email)
    return {"Authorization": f"Bearer {token}"}


def test_vapid_key_generation():
    private_key, public_key = get_or_create_vapid_keys()
    assert private_key is not None
    assert public_key is not None
    assert len(public_key) > 20

    # Verify private key is parseable by py_vapid
    vapid_obj = Vapid.from_string(private_key)
    assert vapid_obj is not None

    # Verify public key is non-empty unpadded base64url string
    assert not public_key.endswith("=")
    assert not private_key.endswith("=")


def test_push_subscription_model(session: Session):
    user = create_test_user(session, email="modeluser@example.com")

    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/test_token",
        p256dh="test_p256dh",
        auth="test_auth",
        user_agent="Mozilla/5.0",
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)

    assert sub.id is not None
    assert sub.user_id == user.id
    assert sub.endpoint == "https://fcm.googleapis.com/fcm/send/test_token"


def test_get_vapid_public_key(client: TestClient, auth_headers: dict):
    response = client.get("/push/vapid-public-key", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert len(data["public_key"]) > 20


def test_get_vapid_public_key_unauthenticated(client: TestClient):
    response = client.get("/push/vapid-public-key")
    assert response.status_code == 401


def test_subscribe_and_unsubscribe_push(
    client: TestClient, auth_headers: dict, session: Session
):
    sub_payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/unique_token_123",
        "keys": {"p256dh": "sample_p256dh_key", "auth": "sample_auth_secret"},
        "user_agent": "Mozilla/5.0",
    }
    # Subscribe
    res_sub = client.post("/push/subscribe", json=sub_payload, headers=auth_headers)
    assert res_sub.status_code == 200
    assert res_sub.json()["status"] == "subscribed"

    # Verify DB record created
    sub = session.exec(
        select(PushSubscription).where(
            PushSubscription.endpoint == sub_payload["endpoint"]
        )
    ).first()
    assert sub is not None
    assert sub.p256dh == "sample_p256dh_key"

    # Unsubscribe
    unsub_payload = {"endpoint": "https://fcm.googleapis.com/fcm/send/unique_token_123"}
    res_unsub = client.request(
        "DELETE", "/push/unsubscribe", json=unsub_payload, headers=auth_headers
    )
    assert res_unsub.status_code == 200
    assert res_unsub.json()["status"] == "unsubscribed"

    # Verify DB record deleted
    sub_deleted = session.exec(
        select(PushSubscription).where(
            PushSubscription.endpoint == sub_payload["endpoint"]
        )
    ).first()
    assert sub_deleted is None


@patch("app.notifications.webpush")
def test_send_test_push(mock_webpush, client: TestClient, auth_headers: dict):
    # Try sending test push before subscribing -> expect 400
    res_empty = client.post("/push/test", headers=auth_headers)
    assert res_empty.status_code == 400

    # Subscribe first
    sub_res = client.post(
        "/push/subscribe",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/test_token_456",
            "keys": {"p256dh": "dh", "auth": "au"},
        },
        headers=auth_headers,
    )
    assert sub_res.status_code == 200

    # Test send test push
    res = client.post("/push/test", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["delivered"] == 1
    assert mock_webpush.called


def test_dispatch_web_push_notification(session: Session):
    from app.notifications import dispatch_web_push_notification

    user = create_test_user(session, email="dispatchuser@example.com")
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/dispatch_token",
        p256dh="dh_val",
        auth="auth_val",
    )
    session.add(sub)
    session.commit()

    with patch("app.notifications.webpush") as mock_webpush:
        res = dispatch_web_push_notification(
            user_id=user.id,
            title="Dispatch Test",
            body="Dispatch Body",
            session=session,
        )
        assert res["delivered"] == 1
        assert res["failed"] == 0
        assert mock_webpush.called

    # Test subscription cleanup on 410 Gone error
    with patch("app.notifications.webpush") as mock_webpush_error:
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_webpush_error.side_effect = WebPushException(
            "Gone", response=mock_response
        )

        res = dispatch_web_push_notification(
            user_id=user.id,
            title="Dispatch Test 2",
            body="Dispatch Body 2",
            session=session,
        )
        assert res["delivered"] == 0
        assert res["failed"] == 1

        # Check sub was deleted
        remaining_sub = session.exec(
            select(PushSubscription).where(PushSubscription.user_id == user.id)
        ).first()
        assert remaining_sub is None


def test_dispatch_web_push_notification_with_hazard_metadata(session: Session):
    from app.notifications import dispatch_web_push_notification
    import json

    user = create_test_user(session, email="hazardpush@example.com")
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/hazard_token",
        p256dh="dh_hazard",
        auth="auth_hazard",
    )
    session.add(sub)
    session.commit()

    with patch("app.notifications.webpush") as mock_webpush:
        res = dispatch_web_push_notification(
            user_id=user.id,
            title="⚠️ Caution: Summit Pass",
            body="Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM.",
            session=session,
            url="/#route-visualizer",
            has_route_hazard=True,
            hazard_count=1,
            primary_hazard_location="Summit Pass",
        )
        assert res["delivered"] == 1
        assert res["failed"] == 0
        assert mock_webpush.called

        # Verify JSON payload has route hazard metadata
        call_kwargs = mock_webpush.call_args[1]
        data = json.loads(call_kwargs["data"])
        assert data["has_route_hazard"] is True
        assert data["hazard_count"] == 1
        assert data["primary_hazard_location"] == "Summit Pass"
        assert data["url"] == "/#route-visualizer"
        assert "Summit Pass" in data["body"]


def test_dispatch_web_push_notification_without_hazard_metadata(session: Session):
    from app.notifications import dispatch_web_push_notification
    import json

    user = create_test_user(session, email="cleanpush@example.com")
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/clean_token",
        p256dh="dh_clean",
        auth="auth_clean",
    )
    session.add(sub)
    session.commit()

    with patch("app.notifications.webpush") as mock_webpush:
        res = dispatch_web_push_notification(
            user_id=user.id,
            title="🏍️ Commute Check: Go",
            body="Enjoy your ride!",
            session=session,
        )
        assert res["delivered"] == 1
        call_kwargs = mock_webpush.call_args[1]
        data = json.loads(call_kwargs["data"])
        assert data["has_route_hazard"] is False
        assert data["hazard_count"] == 0
        assert data["primary_hazard_location"] == ""


def test_dispatch_web_push_notification_from_assessment_object(session: Session):
    from app.notifications import dispatch_web_push_notification
    from app.models import AssessmentResult, Status
    import json

    user = create_test_user(session, email="assesspush@example.com")
    sub = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/assess_token",
        p256dh="dh_assess",
        auth="auth_assess",
    )
    session.add(sub)
    session.commit()

    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=60,
        recommendation="Ride with caution.",
        reasons=["High wind gusts"],
        hazard_pinpoints=[
            {
                "location": "Eagle Point",
                "hazard": "High wind gusts",
                "value": "26 mph",
                "time": "08:15 AM",
            }
        ],
    )

    with patch("app.notifications.webpush") as mock_webpush:
        res = dispatch_web_push_notification(
            user_id=user.id,
            title="Commute Check: Caution",
            body="Alert body",
            session=session,
            assessment=assessment,
        )
        assert res["delivered"] == 1
        call_kwargs = mock_webpush.call_args[1]
        data = json.loads(call_kwargs["data"])
        assert data["has_route_hazard"] is True
        assert data["hazard_count"] == 1
        assert data["primary_hazard_location"] == "Eagle Point"


@patch("app.notifications.webpush")
def test_send_test_push_with_hazard_metadata_api(
    mock_webpush, client: TestClient, auth_headers: dict
):
    # Subscribe first
    sub_res = client.post(
        "/push/subscribe",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/api_hazard_token",
            "keys": {"p256dh": "dh_api", "auth": "auth_api"},
        },
        headers=auth_headers,
    )
    assert sub_res.status_code == 200

    # Post /push/test with hazard metadata
    res = client.post(
        "/push/test",
        json={
            "title": "Hazard Commute Test",
            "body": "Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM.",
            "url": "/#route-visualizer",
            "has_route_hazard": True,
            "hazard_count": 2,
            "primary_hazard_location": "Summit Pass",
        },
        headers=auth_headers,
    )

    assert res.status_code == 200
    assert res.json()["delivered"] == 1
    assert mock_webpush.called

    import json

    call_kwargs = mock_webpush.call_args[1]
    data = json.loads(call_kwargs["data"])
    assert data["has_route_hazard"] is True
    assert data["hazard_count"] == 2
    assert data["primary_hazard_location"] == "Summit Pass"
    assert data["url"] == "/#route-visualizer"
    assert "Summit Pass" in data["body"]
