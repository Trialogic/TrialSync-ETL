"""CLI command for starting the ETL scheduler."""

import signal
import sys
import time

import click
import structlog

from src.etl.scheduler import ETLScheduler

logger = structlog.get_logger(__name__)


@click.command()
@click.option(
    "--reload-interval",
    type=int,
    default=300,
    help="Reload schedules from database every N seconds (default: 300)",
)
def scheduler(reload_interval: int) -> None:
    """Start the ETL job scheduler.

    This command starts a background scheduler that executes ETL jobs
    based on their cron schedules stored in the database.
    """
    scheduler_instance = ETLScheduler()

    def signal_handler(sig, frame):
        """Handle shutdown signals."""
        logger.info("shutdown_signal_received")
        scheduler_instance.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        scheduler_instance.start()

        logger.info(
            "scheduler_running",
            reload_interval=reload_interval,
        )

        # Reload schedules periodically
        last_reload = time.time()
        while True:
            time.sleep(10)  # Check every 10 seconds

            # Reload if interval has passed
            if time.time() - last_reload >= reload_interval:
                logger.info("reloading_schedules")
                scheduler_instance.reload_jobs()
                last_reload = time.time()

    except KeyboardInterrupt:
        logger.info("scheduler_interrupted")
        scheduler_instance.stop()
    except Exception as e:
        logger.error("scheduler_error", error=str(e))
        scheduler_instance.stop()
        sys.exit(1)

