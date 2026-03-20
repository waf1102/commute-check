import pytest
from unittest.mock import AsyncMock, patch
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

@pytest.mark.asyncio
async def test_format_discord_payload(service, sample_assessment):
    payload = service._format_discord_payload(sample_assessment)
    
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "Commute Check: Go" in embed["title"]
    assert embed["color"] == 3066993  # Green
    assert any(f["name"] == "Score" and f["value"] == "100/100" for f in embed["fields"])

@pytest.mark.asyncio
async def test_format_generic_payload(service, sample_assessment):
    payload = service._format_generic_payload(sample_assessment)
    assert payload["status"] == "Go"
    assert payload["score"] == 100

@pytest.mark.asyncio
async def test_send_notification_discord_detection(service, sample_assessment):
    discord_url = "https://discord.com/api/webhooks/123/abc"
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 204
        
        await service.send_notification(discord_url, sample_assessment)
        
        # Check that it was called with discord payload (has embeds)
        args, kwargs = mock_post.call_args
        assert "embeds" in kwargs["json"]

@pytest.mark.asyncio
async def test_send_notification_generic(service, sample_assessment):
    generic_url = "https://example.com/webhook"
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.status_code = 200
        
        await service.send_notification(generic_url, sample_assessment)
        
        # Check that it was called with generic payload (no embeds)
        args, kwargs = mock_post.call_args
        assert "embeds" not in kwargs["json"]
        assert kwargs["json"]["status"] == "Go"

@pytest.mark.asyncio
async def test_send_notification_failure(service, sample_assessment):
    url = "https://example.com/webhook"
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = Exception("Network error")
        
        result = await service.send_notification(url, sample_assessment)
        assert result is False

@pytest.mark.parametrize("status,expected_color", [
    (Status.GO, 3066993),
    (Status.CAUTION, 16776960),
    (Status.NO_GO, 15158332),
])
def test_status_color_mapping(service, sample_assessment, status, expected_color):
    sample_assessment.status = status
    payload = service._format_discord_payload(sample_assessment)
    assert payload["embeds"][0]["color"] == expected_color
