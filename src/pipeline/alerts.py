import os
import logging
import requests

from pipeline.interfaces import Notifier

logger = logging.getLogger("USGSPipeline.Alerts")

_SENSITIVE_PREFIXES = ("postgresql://", "postgres://", "http://", "https://")


def _sanitize(message: str) -> str:
    """Strip connection strings or URLs from error messages before sending to Slack."""
    for prefix in _SENSITIVE_PREFIXES:
        if prefix in message:
            return "[redacted — message may contain sensitive connection details]"
    return message


class SlackNotifier(Notifier):
    """Sends pipeline failure alerts to Slack via an Incoming Webhook."""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    def notify_failure(self, error: Exception, context_stage: str) -> None:
        if not self.webhook_url:
            logger.warning("Slack alert skipped: SLACK_WEBHOOK_URL is not set.")
            return

        payload = {
            "text": "🚨 *Data Pipeline Execution Failure* 🚨",
            "attachments": [
                {
                    "color": "#FF0000",
                    "fields": [
                        {"title": "Pipeline", "value": "USGS Seismic Ingestion", "short": True},
                        {"title": "Failed Stage", "value": context_stage, "short": True},
                        {"title": "Error Type", "value": type(error).__name__, "short": True},
                        {"title": "Error Detail", "value": _sanitize(str(error)), "short": False},
                    ],
                }
            ],
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("Failure alert delivered to Slack.")
        except requests.RequestException as e:
            logger.error(f"Slack notification failed (alert may not have been delivered): {e}")
