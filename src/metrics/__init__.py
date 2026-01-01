"""Prometheus metrics for TrialSync ETL."""

from typing import Optional

from src.metrics.collector import MetricsCollector

__all__ = ["MetricsCollector", "get_metrics_collector"]

# Singleton instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

