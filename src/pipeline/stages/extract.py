import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pipeline.interfaces import PipelineStage
from pipeline.config import PipelineConfig

logger = logging.getLogger("USGSPipeline.Extractor")


class USGSExtractor(PipelineStage):
    """Fetches GeoJSON earthquake records from the USGS API with retry/backoff."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def _get_date_range(self):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=self.config.lookback_days)
        return start_date.isoformat(), end_date.isoformat()

    def execute(self, data: Any = None) -> List[Dict[str, Any]]:
        start, end = self._get_date_range()
        params = {
            "format": "geojson",
            "starttime": start,
            "endtime": end,
            "minmagnitude": self.config.min_magnitude,
        }

        logger.info(f"Extracting USGS data from {start} to {end}...")

        for attempt in range(self.config.max_retries):
            try:
                response = requests.get(
                    self.config.base_url,
                    params=params,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()

                try:
                    features = response.json().get("features", [])
                except ValueError as e:
                    raise RuntimeError(
                        f"USGS returned a non-JSON response: {e}"
                    ) from e

                logger.info(f"Extraction successful — {len(features)} records retrieved.")
                return features

            except (requests.exceptions.RequestException, RuntimeError) as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_retries} failed: {e}"
                )
                if attempt < self.config.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff; skip on final attempt

        logger.error("Max retries exhausted.")
        raise ConnectionError("Pipeline halted: could not reach the USGS API.")
