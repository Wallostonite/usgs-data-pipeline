"""Unit tests for USGSExtractor."""
import pytest
import responses
from pipeline.config import PipelineConfig
from pipeline.stages.extract import USGSExtractor

SAMPLE_GEOJSON = {
    "features": [
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
}


@pytest.fixture
def config():
    return PipelineConfig(
        base_url="https://earthquake.usgs.gov/fdsnws/event/1/query",
        min_magnitude=2.5,
        lookback_days=1,
        max_retries=2,
        timeout=5,
        db_url="postgresql://user:pass@localhost/test",
    )


@responses.activate
def test_execute_returns_features(config):
    responses.add(
        responses.GET,
        config.base_url,
        json=SAMPLE_GEOJSON,
        status=200,
    )
    extractor = USGSExtractor(config)
    result = extractor.execute()
    assert len(result) == 1
    assert result[0]["id"] == "us1000abc"


@responses.activate
def test_execute_retries_on_failure(config):
    responses.add(responses.GET, config.base_url, status=500)
    responses.add(responses.GET, config.base_url, json=SAMPLE_GEOJSON, status=200)
    extractor = USGSExtractor(config)
    result = extractor.execute()
    assert len(result) == 1


@responses.activate
def test_execute_raises_after_max_retries(config):
    for _ in range(config.max_retries):
        responses.add(responses.GET, config.base_url, status=503)
    extractor = USGSExtractor(config)
    with pytest.raises(ConnectionError):
        extractor.execute()
