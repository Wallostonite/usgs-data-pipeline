import logging
import time

from pipeline.config import PipelineConfig
from pipeline.alerts import SlackNotifier
from pipeline.stages import USGSExtractor, SeismicTransformer, PostgreSQLLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("USGSPipeline.Orchestrator")


class SeismicPipeline:
    """Orchestrates the Extract → Transform → Load sequence."""

    def __init__(self):
        self.config = PipelineConfig()
        self.extractor = USGSExtractor(self.config)
        self.transformer = SeismicTransformer()
        self.loader = PostgreSQLLoader(self.config.db_url)
        self.notifier = SlackNotifier()

    def run(self):
        logger.info("=== PIPELINE BATCH EXECUTION STARTED ===")
        start_time = time.time()
        current_stage = "Initialization"

        try:
            # setup() is called here (not in __init__) so DB errors are caught
            # and routed through the notifier like any other stage failure.
            current_stage = "Schema Setup"
            self.loader.setup()

            current_stage = "Extraction"
            raw_payload = self.extractor.execute()

            current_stage = "Transformation"
            clean_payload = self.transformer.execute(raw_payload)

            current_stage = "Loading"
            self.loader.execute(clean_payload)

            logger.info("=== PIPELINE BATCH EXECUTION COMPLETED SUCCESSFULLY ===")

        except Exception as e:
            logger.critical(f"Pipeline crashed during {current_stage!r}: {e}")
            self.notifier.notify_failure(e, current_stage)
            raise

        finally:
            logger.info(f"Total elapsed: {time.time() - start_time:.2f}s")


if __name__ == "__main__":
    pipeline = SeismicPipeline()
    pipeline.run()
