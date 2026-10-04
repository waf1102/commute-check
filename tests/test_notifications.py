import pytest
from unittest.mock import MagicMock, patch
import apprise
from app.notifications import NotificationService
from app.models import Status, AssessmentResult, HourlyWeather


@pytest.fixture
def service():
    return NotificationService()


@pytest.fixture
def sample_assessment():
    return AssessmentResult(
        status=Status.GO,
        score=100,
        recommendation="Perfect day for a ride!",
        reasons=["Weather is ideal."],
        details=HourlyWeather(
            temperature=72.5,
            apparent_temp=75.0,
            wind_speed=5.0,
            wind_gusts=8.0,
            precip_prob=0.0,
            weather_code=0,
        ),
    )


def test_format_message(service, sample_assessment):
    title, body = service._format_message(sample_assessment)
    assert "Commute Check: Go" in title
    assert "Perfect day for a ride!" in body
    assert "Score: 100/100" in body
    assert "Temp: 72.5°F" in body


def test_format_message_with_wind_hazard_pinpoint(service):
    # Commute with wind hazard pinpoint matching prompt specification
    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=60,
        recommendation="Ride with caution.",
        reasons=["High wind gusts"],
        hazard_pinpoints=[
            {
                "location": "Summit Pass",
                "hazard": "High wind gusts",
                "value": "28 mph",
                "time": "08:25 AM",
            }
        ],
    )
    title, body = service._format_message(assessment, leg_type="outbound")
    expected_body = "Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM."
    assert body == expected_body
    assert "Caution" in title


def test_format_message_with_rain_hazard(service):
    # Commute with rain hazard on evening return
    assessment = AssessmentResult(
        status=Status.NO_GO,
        score=25,
        recommendation="Riding not recommended.",
        reasons=["Heavy rain"],
        hazard_pinpoints=[
            {
                "location": "Valley Road",
                "hazard": "rain",
                "value": "85%",
                "time": "05:15 PM",
            }
        ],
    )
    title, body = service._format_message(assessment, leg_type="return")
    expected_body = "Commute Check: No-Go for Evening Commute. ⚠️ Heavy rain (85%) near Valley Road at ~05:15 PM."
    assert body == expected_body
    assert "No-Go" in title


def test_format_message_with_low_temp_hazard(service):
    # Commute with low temperature hazard
    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=55,
        recommendation="Ride with caution.",
        reasons=["Low temperature"],
        hazard_pinpoints=[
            {
                "location": "Mountain Ridge",
                "hazard": "low temperature",
                "value": "28°F",
                "time": "07:30 AM",
            }
        ],
    )
    title, body = service._format_message(assessment, leg_type="outbound")
    expected_body = "Commute Check: Caution for Morning Commute. ⚠️ Low temperature (28°F) near Mountain Ridge at ~07:30 AM."
    assert body == expected_body


def test_format_message_with_custom_commute_name(service):
    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=65,
        recommendation="Ride with caution.",
        reasons=["High wind"],
        commute_name="Pacific Coast Ride",
        hazard_pinpoints=[
            {
                "location": "Bixby Bridge",
                "hazard": "High wind gusts",
                "value": "35 mph",
                "time": "09:40 AM",
            }
        ],
    )
    title, body = service._format_message(assessment)
    assert "Commute Check: Caution for Pacific Coast Ride." in body
    assert "⚠️ High wind gusts (35 mph) near Bixby Bridge at ~09:40 AM." in body


def test_format_message_with_waypoint_risks(service):
    # Assessment using waypoint_risks attribute
    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=60,
        recommendation="Ride with caution.",
        reasons=["High wind gusts"],
        waypoint_risks=[
            {
                "location_name": "Ridge Crossing",
                "parameter": "wind",
                "value": "30 mph",
                "encounter_time": "08:15 AM",
            }
        ],
    )
    title, body = service._format_message(assessment, leg_type="outbound")
    assert "Commute Check: Caution for Morning Commute." in body
    assert "⚠️ High wind gusts (30 mph) near Ridge Crossing at ~08:15 AM." in body


def test_format_message_with_multiple_hazards(service):
    assessment = AssessmentResult(
        status=Status.NO_GO,
        score=20,
        recommendation="Riding not recommended.",
        reasons=["Extreme weather"],
        hazard_pinpoints=[
            {
                "location": "Summit Pass",
                "hazard": "High wind gusts",
                "value": "32 mph",
                "time": "08:10 AM",
            },
            {
                "location": "River Valley",
                "hazard": "rain",
                "value": "90%",
                "time": "08:45 AM",
            },
        ],
    )
    title, body = service._format_message(assessment, leg_type="outbound")
    assert "⚠️ High wind gusts (32 mph) near Summit Pass at ~08:10 AM." in body
    assert "⚠️ Heavy rain (90%) near River Valley at ~08:45 AM." in body


@pytest.mark.asyncio
async def test_send_notification_apprise(service, sample_assessment):
    with patch("apprise.Apprise") as mock_apprise_cls:
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True
        mock_apprise_cls.return_value = mock_apprise

        result = await service.send_notification(
            "json://example.com/webhook", sample_assessment
        )
        assert result is True
        mock_apprise.add.assert_called_with("json://example.com/webhook")
        mock_apprise.notify.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_apprise_with_hazards(service):
    assessment = AssessmentResult(
        status=Status.CAUTION,
        score=60,
        recommendation="Ride with caution.",
        reasons=["High wind gusts"],
        hazard_pinpoints=[
            {
                "location": "Summit Pass",
                "hazard": "High wind gusts",
                "value": "28 mph",
                "time": "08:25 AM",
            }
        ],
    )
    with patch("apprise.Apprise") as mock_apprise_cls:
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True
        mock_apprise_cls.return_value = mock_apprise

        result = await service.send_notification(
            "json://example.com/webhook", assessment, leg_type="outbound"
        )
        assert result is True
        call_kwargs = mock_apprise.notify.call_args[1]
        assert (
            "Commute Check: Caution for Morning Commute. ⚠️ High wind gusts (28 mph) near Summit Pass at ~08:25 AM."
            in call_kwargs["body"]
        )


def test_extract_hazard_pinpoints_dict_payload(service):
    # Assessment passed as standard dictionary
    payload = {
        "status": "Caution",
        "hazard_pinpoints": [
            {
                "location": "Ridge Point",
                "hazard": "High wind gusts",
                "value": "35 mph",
                "time": "08:15 AM",
            }
        ],
    }
    pts = service.extract_hazard_pinpoints(payload)
    assert len(pts) == 1
    assert pts[0]["location"] == "Ridge Point"
    assert pts[0]["hazard"] == "High wind gusts"


def test_extract_hazard_pinpoints_nested_dict_payload(service):
    # Nested under 'assessment'
    nested_payload = {
        "assessment": {
            "status": "No-Go",
            "hazard_pinpoints": [
                {
                    "location_name": "Valley Bridge",
                    "parameter": "Heavy rain",
                    "value": "90%",
                    "encounter_time": "07:45 AM",
                }
            ],
        }
    }
    pts = service.extract_hazard_pinpoints(nested_payload)
    assert len(pts) == 1
    assert pts[0]["location"] == "Valley Bridge"
    assert pts[0]["hazard"] == "Heavy rain"

    # Deeply nested under 'data' -> 'assessment'
    deep_nested = {"data": nested_payload}
    pts_deep = service.extract_hazard_pinpoints(deep_nested)
    assert len(pts_deep) == 1
    assert pts_deep[0]["location"] == "Valley Bridge"


def test_extract_hazard_pinpoints_raw_list(service):
    # Assessment passed directly as a list of hazard pinpoints
    raw_list = [
        {"location": "Pass Summit", "hazard": "ice", "time": "06:30 AM"}
    ]
    pts = service.extract_hazard_pinpoints(raw_list)
    assert len(pts) == 1
    assert pts[0]["location"] == "Pass Summit"


def test_extract_hazard_pinpoints_skip_safe_waypoints(service):
    # Safe waypoints without hazards should be skipped, but waypoints with hazards or non-Go status kept
    payload = {
        "waypoints": [
            {"name": "Stop 1", "status": "Go"},
            {"name": "Stop 2", "status": "Caution", "hazard": "High wind gusts", "value": "30 mph"},
            {"name": "Stop 3", "status": {"value": "Go"}},
        ]
    }
    pts = service.extract_hazard_pinpoints(payload)
    assert len(pts) == 1
    assert pts[0]["name"] == "Stop 2"


def test_format_hazard_alert_with_dict_payload(service):
    # Correctly parses status and commute info from dict
    dict_assessment = {
        "status": "No-Go",
        "commute_name": "Mountain Express",
        "hazard_pinpoints": [
            {
                "location": "Echo Summit",
                "hazard": "rain",
                "value": "95%",
                "time": "08:00 AM",
            }
        ],
    }
    alert = service.format_hazard_alert(dict_assessment)
    assert "Commute Check: No-Go for Mountain Express." in alert
    assert "⚠️ Heavy rain (95%) near Echo Summit at ~08:00 AM." in alert


def test_format_hazard_alert_with_nested_dict_and_status_mapping(service):
    # Tests status case normalization and nested dictionary lookup
    nested = {
        "assessment": {
            "status": "caution",
            "leg_type": "return",
            "hazard_pinpoints": [
                {
                    "location": "Cold Springs",
                    "hazard": "low temperature",
                    "value": 0,  # 0 should not be dropped
                    "time": "06:00 AM",
                }
            ],
        }
    }
    alert = service.format_hazard_alert(nested)
    assert "Commute Check: Caution for Evening Commute." in alert
    assert "0°F" in alert
    assert "near Cold Springs" in alert


def test_format_hazard_alert_missing_attributes(service):
    # Assessment with missing attributes should never raise AttributeError
    sparse = {"status": "Caution"}
    alert = service.format_hazard_alert(sparse)
    assert alert == "Commute Check: Caution for Commute."


def test_format_message_with_dict_without_pinpoints(service):
    # Formats summary message safely when assessment is a dict with no pinpoints
    dict_assessment = {
        "status": "Go",
        "score": 95,
        "recommendation": "Great weather ahead!",
        "reasons": ["Clear skies", "Mild breeze"],
        "weather": {
            "temperature": 68.0,
            "wind_speed": 4.5,
            "precip_prob": 5.0,
        },
    }
    title, body = service._format_message(dict_assessment, leg_type="outbound")
    assert "Commute Check (Morning Outbound): Go" in title
    assert "Great weather ahead!" in body
    assert "Score: 95/100" in body
    assert "Temp: 68.0°F" in body
    assert "Wind: 4.5 mph" in body
    assert "Clear skies" in body


@pytest.mark.asyncio
async def test_send_notification_apprise_with_dict_payload(service):
    # Verify send_notification succeeds and properly categorizes Apprise notification type
    dict_assessment = {
        "status": "No-Go",
        "score": 30,
        "hazard_pinpoints": [
            {
                "location": "Storm Ridge",
                "hazard": "High wind gusts",
                "value": "45 mph",
                "time": "09:00 AM",
            }
        ],
    }
    with patch("apprise.Apprise") as mock_apprise_cls:
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True
        mock_apprise_cls.return_value = mock_apprise

        result = await service.send_notification(
            "json://example.com/webhook", dict_assessment, leg_type="outbound"
        )
        assert result is True
        mock_apprise.notify.assert_called_once()
        call_kwargs = mock_apprise.notify.call_args[1]
        assert call_kwargs["notify_type"] == apprise.NotifyType.FAILURE
        assert "Commute Check: No-Go for Morning Commute." in call_kwargs["body"]
        assert "Storm Ridge" in call_kwargs["body"]

