import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import Column, DateTime, Float, JSON, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from pipeline.interfaces import PipelineStage

logger = logging.getLogger("USGSPipeline.Loader")

Base = declarative_base()


class EarthquakeRecord(Base):
    """ORM model for the earthquake_events table."""

    __tablename__ = "earthquake_events"

    id = Column(String, primary_key=True)
    magnitude = Column(Float, nullable=True)
    location = Column(String, nullable=True)
    timestamp_utc = Column(DateTime, nullable=False, index=True)
    coordinates = Column(JSON, nullable=False)
    status = Column(String, nullable=True)


class PostgreSQLLoader(PipelineStage):
    """Manages connection pooling, DDL, and idempotent bulk upserts into PostgreSQL."""

    def __init__(self, db_url: str):
        self.engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
        )
        self.Session = sessionmaker(bind=self.engine)

    def setup(self) -> None:
        """Create the target table if it does not exist. Call before execute()."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database schema verified.")
        except SQLAlchemyError as e:
            logger.critical(f"Schema initialization failed: {e}")
            raise

    def execute(self, data: List[Dict[str, Any]]) -> None:
        if not data:
            logger.warning("No records to load — skipping database write.")
            return

        logger.info(f"Opening transaction for {len(data)} records...")

        with self.Session() as session:
            try:
                for item in data:
                    session.merge(
                        EarthquakeRecord(
                            id=item.get("id"),
                            magnitude=item.get("magnitude"),
                            location=item.get("location"),
                            timestamp_utc=datetime.fromisoformat(
                                item.get("timestamp_utc")
                            ),
                            coordinates=item.get("coordinates"),
                            status=item.get("status"),
                        )
                    )

                session.commit()
                logger.info("Transaction committed successfully.")

            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Transaction failed — rollback applied: {e}")
                raise
