"""Unit tests for SeismicTransformer."""
import pytest
from pipeline.stages.transform import SeismicTransformer

RAW_VALID = [
    {
        "id": "us1000abc",
        "properties": {
            "mag": 3.5,
            "place": "10km N of Test City",
            "time": 1700000000000,
            "status": "reviewed",
        },
        "geometry": {"coordinates": [-118.0, 34.0, 10.0]},
    }
]

RAW_MISSING_TIME = [
    {
        "id": "us_no_time",
        "properties": {"mag": 2.0, "place": "Somewhere", "time": None, "status": "automatic"},
        "geometry": {"coordinates": [-100.0, 30.0, 5.0]},
    }
]

RAW_MISSING_COORDS = [
    {
        "id": "us_bad_geom",
        "properties": {"mag": 2.0, "place": "Somewhere", "time": 1700000000000, "status": "automatic"},
        "geometry": {"coordinates": [-100.0]},  # too short
    }
]


@pytest.fixture
def transformer():
    return SeismicTransformer()


def test_valid_record_is_transformed(transformer):
    result = transformer.execute(RAW_VALID)
    assert len(result) == 1
    rec = result[0]
    assert rec["id"] == "us1000abc"
    assert rec["magnitude"] == 3.5
    assert rec["coordinates"]["latitude"] == 34.0
    assert "timestamp_utc" in rec


def test_record_missing_time_is_skipped(transformer):
    result = transformer.execute(RAW_MISSING_TIME)
    assert result == []


def test_record_with_short_coords_is_skipped(transformer):
    result = transformer.execute(RAW_MISSING_COORDS)
    assert result == []


def test_none_input_returns_empty_list(transformer):
    result = transformer.execute(None)
    assert result == []


def test_empty_input_returns_empty_list(transformer):
    result = transformer.execute([])
    assert result == []
