import logging
from datetime import datetime
from typing import Any, Dict, List

from pipeline.interfaces import PipelineStage

logger = logging.getLogger("USGSPipeline.Transformer")


class SeismicTransformer(PipelineStage):
    """Validates fields, strips malformed records, and normalizes timestamps to UTC."""

    def execute(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if raw_data is None:
            logger.warning("Transformer received None — treating as empty.")
            return []

        logger.info(f"Transforming {len(raw_data)} raw records...")
        transformed: List[Dict[str, Any]] = []

        for item in raw_data:
            try:
                props = item.get("properties", {})
                geom = item.get("geometry", {}).get("coordinates", [])

                if not props or len(geom) < 3:
                    continue

                raw_time = props.get("time")
                if raw_time is None:
                    logger.warning(
                        f"Skipping record {item.get('id')!r}: missing 'time' field."
                    )
                    continue

                transformed.append(
                    {
                        "id": item.get("id"),
                        "magnitude": props.get("mag"),
                        "location": props.get("place"),
                        "timestamp_utc": datetime.utcfromtimestamp(
                            raw_time / 1000.0
                        ).isoformat(),
                        "coordinates": {
                            "longitude": geom[0],
                            "latitude": geom[1],
                            "depth_km": geom[2],
                        },
                        "status": props.get("status"),
                    }
                )

            except (ValueError, IndexError, AttributeError, TypeError) as e:
                logger.error(f"Skipping malformed record {item.get('id')!r}: {e}")
                continue

        logger.info(f"Transformation complete — {len(transformed)} valid records ready.")
        return transformed
