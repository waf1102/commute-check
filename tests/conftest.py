import os
import glob
import pytest


@pytest.fixture(autouse=True, scope="session")
def cleanup_all_sqlite_test_dbs():
    yield
    for pattern in [
        "test*.db",
        "test.db",
        "test_analytics.db",
        "test_push.db",
        "test_scheduler.db",
    ]:
        for db_file in glob.glob(pattern):
            try:
                os.remove(db_file)
            except OSError:
                pass


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch, tmp_path):
    """Tests must replace provider calls explicitly, never make live forecasts."""
    import httpx

    monkeypatch.setenv("VAPID_KEY_FILE", str(tmp_path / "vapid-keys.json"))
    from app.main import client_instance, scheduler
    from app.client import _default_weather_client

    client_instance._cache.clear()
    _default_weather_client._cache.clear()

    async def blocked(*args, **kwargs):
        raise AssertionError("Unexpected external HTTP request in test")

    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    yield
    scheduler.remove_all_jobs()
