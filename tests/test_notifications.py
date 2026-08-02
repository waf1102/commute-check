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
            weather_code=0
        )
    )

def test_format_message(service, sample_assessment):
    title, body = service._format_message(sample_assessment)
    assert "Commute Check: Go" in title
    assert "Perfect day for a ride!" in body
    assert "Score: 100/100" in body
    assert "Temp: 72.5°F" in body

@pytest.mark.asyncio
async def test_send_notification_apprise(service, sample_assessment):
    with patch("apprise.Apprise") as mock_apprise_cls:
        mock_apprise = MagicMock()
        mock_apprise.notify.return_value = True
        mock_apprise_cls.return_value = mock_apprise

        result = await service.send_notification("json://example.com/webhook", sample_assessment)
        assert result is True
        mock_apprise.add.assert_called_with("json://example.com/webhook")
        mock_apprise.notify.assert_called_once()
