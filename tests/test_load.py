"""Unit tests for PostgreSQLLoader."""
import pytest
from unittest.mock import MagicMock, patch, call
from pipeline.stages.load import PostgreSQLLoader, EarthquakeRecord

SAMPLE_RECORDS = [
    {
        "id": "us1000abc",
        "magnitude": 3.5,
        "location": "10km N of Test City",
        "timestamp_utc": "2023-11-14T22:13:20",
        "coordinates": {"longitude": -118.0, "latitude": 34.0, "depth_km": 10.0},
        "status": "reviewed",
    }
]


@pytest.fixture
def loader():
    with patch("pipeline.stages.load.create_engine"), \
         patch("pipeline.stages.load.sessionmaker"):
        return PostgreSQLLoader("postgresql://user:pass@localhost/test")


def test_execute_skips_empty_data(loader, caplog):
    loader.execute([])
    assert "No records to load" in caplog.text


def test_execute_merges_records(loader):
    mock_session = MagicMock()
    loader.Session.return_value.__enter__ = MagicMock(return_value=mock_session)
    loader.Session.return_value.__exit__ = MagicMock(return_value=False)

    loader.execute(SAMPLE_RECORDS)

    mock_session.merge.assert_called_once()
    mock_session.commit.assert_called_once()


def test_execute_rolls_back_on_error(loader):
    from sqlalchemy.exc import SQLAlchemyError

    mock_session = MagicMock()
    mock_session.merge.side_effect = SQLAlchemyError("integrity error")
    loader.Session.return_value.__enter__ = MagicMock(return_value=mock_session)
    loader.Session.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(SQLAlchemyError):
        loader.execute(SAMPLE_RECORDS)

    mock_session.rollback.assert_called_once()
