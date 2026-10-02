import os
import glob
import pytest

@pytest.fixture(autouse=True, scope="session")
def cleanup_all_sqlite_test_dbs():
    yield
    for pattern in ["test*.db", "test.db", "test_analytics.db", "test_push.db", "test_scheduler.db"]:
        for db_file in glob.glob(pattern):
            try:
                os.remove(db_file)
            except OSError:
                pass
