import pytest
from app.models import Status, HourlyWeather, Commute
from app.engine import AssessmentEngine


@pytest.fixture
def engine():
    return AssessmentEngine()


@pytest.fixture
def thresholds():
    return Commute(lat=0.0, lon=0.0, schedule_time="08:00")


def test_perfect_day(engine, thresholds):
    weather = HourlyWeather(
        temperature=75.0,
        apparent_temp=75.0,
        wind_speed=5.0,
        wind_gusts=7.0,
        precip_prob=0.0,
        weather_code=0,
    )
    result = engine.assess(weather, thresholds)
    assert result.status == Status.GO
    assert result.score == 100
    assert "Clear conditions" in result.reasons


def test_ice_risk(engine, thresholds):
    weather = HourlyWeather(
        temperature=32.0,
        apparent_temp=30.0,
        wind_speed=10.0,
        wind_gusts=15.0,
        precip_prob=0.0,
        weather_code=0,
    )
    result = engine.assess(weather, thresholds)
    assert result.status == Status.NO_GO
    assert result.score == 0
    assert "Temperature below safety threshold (ice risk)" in result.reasons


def test_gale_wind(engine, thresholds):
    weather = HourlyWeather(
        temperature=60.0,
        apparent_temp=60.0,
        wind_speed=40.0,
        wind_gusts=50.0,
        precip_prob=0.0,
        weather_code=0,
    )
    result = engine.assess(weather, thresholds)
    assert result.status == Status.NO_GO
    assert result.score == 0
    assert "Extreme wind speeds" in result.reasons


def test_high_rain_probability(engine, thresholds):
    weather = HourlyWeather(
        temperature=65.0,
        apparent_temp=65.0,
        wind_speed=10.0,
        wind_gusts=15.0,
        precip_prob=80.0,
        weather_code=3,
    )
    result = engine.assess(weather, thresholds)
    assert result.status == Status.NO_GO
    assert "High probability of rain" in result.reasons


def test_chilly_morning_caution(engine, thresholds):
    weather = HourlyWeather(
        temperature=45.0,
        apparent_temp=38.0,  # Wind chill
        wind_speed=10.0,
        wind_gusts=15.0,
        precip_prob=0.0,
        weather_code=0,
    )
    # Default thresholds for Commute: min_temp_caution=45.0, min_temp_no_go=38.0
    # Wait, apparent_temp=38.0 is min_temp_no_go.
    # AssessmentEngine: if weather.apparent_temp < thresholds.min_temp_no_go: status=NO_GO
    # If apparent_temp is 38.0, it is NOT < 38.0.
    # Then: if weather.apparent_temp < thresholds.min_temp_caution: score -= 30, reasons.append("Low temperature")
    # 38.0 < 45.0 is true. score = 100 - 30 = 70.
    result = engine.assess(weather, thresholds)
    assert result.status == Status.CAUTION
    assert result.score == 70
    assert "Low temperature" in result.reasons


def test_dangerous_weather_code(engine, thresholds):
    weather = HourlyWeather(
        temperature=45.0,
        apparent_temp=40.0,
        wind_speed=10.0,
        wind_gusts=15.0,
        precip_prob=10.0,
        weather_code=95,  # Thunderstorm
    )
    result = engine.assess(weather, thresholds)
    assert result.status == Status.NO_GO
    assert "Dangerous weather conditions (snow/storm)" in result.reasons


def test_assess_route_with_destination_and_return(engine):
    commute = Commute(
        lat=37.7,
        lon=-122.4,
        dest_name="Work",
        dest_lat=37.3,
        dest_lon=-122.0,
        schedule_time="08:00",
        return_schedule_time="17:00",
    )
    # Origin outbound weather (good)
    origin_outbound = HourlyWeather(
        temperature=60.0,
        apparent_temp=58.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    # Destination outbound weather (bad wind)
    dest_outbound = HourlyWeather(
        temperature=60.0,
        apparent_temp=58.0,
        wind_speed=30.0,
        wind_gusts=35.0,
        precip_prob=0.0,
        weather_code=0,
    )
    # Destination return weather (good)
    dest_return = HourlyWeather(
        temperature=65.0,
        apparent_temp=65.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    # Origin return weather (good)
    origin_return = HourlyWeather(
        temperature=62.0,
        apparent_temp=62.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )

    result = engine.assess_route(
        origin_outbound, dest_outbound, dest_return, origin_return, commute
    )
    assert result.overall_status == Status.NO_GO
    assert result.outbound_leg.status == Status.NO_GO
    assert result.outbound_leg.score == 0
    assert "Extreme wind speeds" in result.outbound_leg.reasons
    assert result.return_leg is not None
    assert result.return_leg.status == Status.GO
    assert result.return_leg.score == 100


def test_assess_route_single_location_fallback(engine):
    commute = Commute(
        lat=37.7,
        lon=-122.4,
        schedule_time="08:00",
        return_schedule_time="17:00",
    )
    origin_outbound = HourlyWeather(
        temperature=70.0,
        apparent_temp=70.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    origin_return = HourlyWeather(
        temperature=45.0,
        apparent_temp=40.0,
        wind_speed=10.0,
        wind_gusts=12.0,
        precip_prob=0.0,
        weather_code=0,
    )

    result = engine.assess_route(origin_outbound, None, None, origin_return, commute)
    assert result.outbound_leg.status == Status.GO
    assert result.outbound_leg.score == 100
    assert result.return_leg is not None
    assert result.return_leg.status == Status.CAUTION
    assert result.return_leg.score == 70
    assert result.overall_status == Status.CAUTION
    assert result.overall_score == 70


def test_assess_route_commute_none_defaults(engine):
    origin_outbound = HourlyWeather(
        temperature=70.0,
        apparent_temp=70.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    origin_return = HourlyWeather(
        temperature=65.0,
        apparent_temp=65.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )

    result = engine.assess_route(
        origin_outbound, None, None, origin_return, commute=None
    )
    assert result.overall_status == Status.GO
    assert result.outbound_leg.location_name == "Origin"
    assert result.outbound_leg.schedule_time == "08:00"
    assert result.return_leg is not None
    assert result.return_leg.location_name == "Origin"
    assert result.return_leg.schedule_time == "17:00"


def test_assess_route_asymmetric_dest_return_weather(engine):
    commute = Commute(
        lat=37.7,
        lon=-122.4,
        dest_name="Office",
        dest_lat=37.3,
        dest_lon=-122.0,
        schedule_time="08:30",
        return_schedule_time="17:30",
    )
    origin_outbound = HourlyWeather(
        temperature=70.0,
        apparent_temp=70.0,
        wind_speed=5.0,
        wind_gusts=8.0,
        precip_prob=0.0,
        weather_code=0,
    )
    dest_return = HourlyWeather(
        temperature=45.0,
        apparent_temp=40.0,
        wind_speed=10.0,
        wind_gusts=12.0,
        precip_prob=0.0,
        weather_code=0,
    )

    result = engine.assess_route(origin_outbound, None, dest_return, None, commute)
    assert result.outbound_leg.status == Status.GO
    assert result.return_leg is not None
    assert result.return_leg.status == Status.CAUTION
    assert result.return_leg.location_name == "Office -> Default Commute"
    assert result.return_leg.schedule_time == "17:30"
    assert result.overall_status == Status.CAUTION
