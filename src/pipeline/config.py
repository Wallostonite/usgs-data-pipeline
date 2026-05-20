import os
from dataclasses import dataclass, field


def _get_float_env(key: str, default: str) -> float:
    value = os.getenv(key, default)
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Environment variable {key}={value!r} is not a valid float.")


def _get_int_env(key: str, default: str) -> int:
    value = os.getenv(key, default)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable {key}={value!r} is not a valid integer.")


@dataclass
class PipelineConfig:
    """Central configuration — all values sourced from environment variables."""

    base_url: str = field(
        default="https://earthquake.usgs.gov/fdsnws/event/1/query"
    )
    min_magnitude: float = field(
        default_factory=lambda: _get_float_env("MIN_MAGNITUDE", "2.5")
    )
    lookback_days: int = field(
        default_factory=lambda: _get_int_env("LOOKBACK_DAYS", "1")
    )
    max_retries: int = 3
    timeout: int = 10
    db_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )

    def __post_init__(self):
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable must be set.")
