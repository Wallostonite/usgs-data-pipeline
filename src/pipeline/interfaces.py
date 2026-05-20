from abc import ABC, abstractmethod
from typing import Any


class PipelineStage(ABC):
    """Contract for all ETL stage implementations."""

    @abstractmethod
    def execute(self, data: Any = None) -> Any:
        """Process input and return output for the next stage."""
        pass


class Notifier(ABC):
    """Contract for alert/notification backends."""

    @abstractmethod
    def notify_failure(self, error: Exception, context_stage: str) -> None:
        """Dispatch a failure notification for the given pipeline stage."""
        pass
