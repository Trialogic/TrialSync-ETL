"""Command-line interface for TrialSync ETL.

Provides commands for running jobs, checking status, viewing history, and scheduling.
"""

import json
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.etl import ETLOrchestrator, JobExecutor
from src.cli.scheduler import scheduler

console = Console()
logger = structlog.get_logger(__name__)


@click.group()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """TrialSync ETL command-line interface."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Configure logging
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)


@cli.command()
@click.option(
    "--job-id",
    type=int,
    help="Execute a specific job by ID",
)
@click.option(
    "--all",
    "all_jobs",
    is_flag=True,
    help="Execute all active jobs",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Dry run mode (no database writes)",
)
@click.pass_context
def run(
    ctx: click.Context,
    job_id: Optional[int],
    all_jobs: bool,
    dry_run: bool,
) -> None:
    """Execute ETL jobs."""
    if not job_id and not all_jobs:
        console.print("[red]Error: Must specify --job-id or --all[/red]")
        ctx.exit(1)

    if job_id and all_jobs:
        console.print("[red]Error: Cannot specify both --job-id and --all[/red]")
        ctx.exit(1)

    try:
        if all_jobs:
            console.print("[cyan]Executing all active jobs...[/cyan]")
            orchestrator = ETLOrchestrator()
            results = orchestrator.execute_all_active_jobs(dry_run=dry_run)

            # Display results
            table = Table(title="Job Execution Results")
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="green" if status == "success" else "red")
            table.add_column("Records", justify="right")
            table.add_column("Duration (s)", justify="right")
            table.add_column("Error", style="red")

            for job_id, result in results.items():
                status_color = "green" if result.status == "success" else "red"
                table.add_row(
                    str(job_id),
                    f"[{status_color}]{result.status}[/{status_color}]",
                    str(result.records_loaded),
                    f"{result.duration_seconds:.2f}",
                    result.error_message or "",
                )

            console.print(table)

            # Summary
            successful = sum(1 for r in results.values() if r.status == "success")
            failed = sum(1 for r in results.values() if r.status == "failed")
            skipped = sum(1 for r in results.values() if r.status == "skipped")

            console.print(f"\n[green]Successful: {successful}[/green]")
            if failed > 0:
                console.print(f"[red]Failed: {failed}[/red]")
            if skipped > 0:
                console.print(f"[yellow]Skipped: {skipped}[/yellow]")

        else:
            console.print(f"[cyan]Executing job {job_id}...[/cyan]")
            executor = JobExecutor()
            result = executor.execute_job(job_id=job_id, dry_run=dry_run)

            if result.status == "success":
                console.print(
                    f"[green]✓ Job {job_id} completed successfully[/green]\n"
                    f"  Records loaded: {result.records_loaded}\n"
                    f"  Duration: {result.duration_seconds:.2f}s\n"
                    f"  Run ID: {result.run_id}"
                )
            else:
                console.print(
                    f"[red]✗ Job {job_id} failed[/red]\n"
                    f"  Error: {result.error_message}\n"
                    f"  Run ID: {result.run_id}"
                )
                ctx.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("cli_run_error", error=str(e))
        ctx.exit(1)


@cli.command()
@click.option(
    "--job-id",
    type=int,
    required=True,
    help="Job ID to check status",
)
def status(job_id: int) -> None:
    """View job status."""
    try:
        orchestrator = ETLOrchestrator()
        job_status = orchestrator.get_job_status(job_id)

        if not job_status:
            console.print(f"[red]Job {job_id} not found[/red]")
            return

        # Display status
        table = Table(title=f"Job {job_id} Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Job ID", str(job_status["job_id"]))
        table.add_row("Name", job_status["name"])
        table.add_row("Active", "Yes" if job_status["is_active"] else "No")
        table.add_row(
            "Last Run",
            str(job_status["last_run_at"]) if job_status["last_run_at"] else "Never",
        )
        table.add_row(
            "Last Status",
            job_status["last_run_status"] or "N/A",
        )
        table.add_row(
            "Last Records",
            str(job_status["last_run_records"]) if job_status["last_run_records"] else "N/A",
        )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("cli_status_error", error=str(e))


@cli.command()
@click.option(
    "--job-id",
    type=int,
    help="Filter by job ID",
)
@click.option(
    "--limit",
    type=int,
    default=10,
    help="Number of runs to display (default: 10)",
)
@click.option(
    "--status",
    "status_filter",
    type=click.Choice(["running", "success", "failed"]),
    help="Filter by status",
)
def history(
    job_id: Optional[int],
    limit: int,
    status_filter: Optional[str],
) -> None:
    """View execution history."""
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT r.id, r.job_id, j.name, r.run_status, r.records_loaded,
                       r.started_at, r.completed_at, r.duration_seconds, r.error_message
                FROM dw_etl_runs r
                JOIN dw_etl_jobs j ON r.job_id = j.id
                WHERE 1=1
            """
            params = []

            if job_id:
                query += " AND r.job_id = %s"
                params.append(job_id)

            if status_filter:
                query += " AND r.run_status = %s"
                params.append(status_filter)

            query += " ORDER BY r.started_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            runs = cursor.fetchall()

            if not runs:
                console.print("[yellow]No runs found[/yellow]")
                return

            # Display history
            table = Table(title="Execution History")
            table.add_column("Run ID", style="cyan")
            table.add_column("Job ID", style="cyan")
            table.add_column("Job Name", style="green")
            table.add_column("Status", style="green")
            table.add_column("Records", justify="right")
            table.add_column("Started", style="blue")
            table.add_column("Duration (s)", justify="right")

            for run in runs:
                run_id, job_id_val, job_name, run_status, records, started_at, completed_at, duration, error = run

                status_color = (
                    "green"
                    if run_status == "success"
                    else "red"
                    if run_status == "failed"
                    else "yellow"
                )

                table.add_row(
                    str(run_id),
                    str(job_id_val),
                    job_name,
                    f"[{status_color}]{run_status}[/{status_color}]",
                    str(records) if records else "0",
                    str(started_at) if started_at else "N/A",
                    str(duration) if duration else "N/A",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("cli_history_error", error=str(e))


@cli.command()
@click.option(
    "--run-id",
    type=int,
    required=True,
    help="Run ID to retry",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Dry run mode",
)
@click.pass_context
def retry(
    ctx: click.Context,
    run_id: int,
    dry_run: bool,
) -> None:
    """Retry a failed job run."""
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        # Get run details
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT job_id, parameters
                FROM dw_etl_runs
                WHERE id = %s
                """,
                (run_id,),
            )

            run = cursor.fetchone()
            if not run:
                console.print(f"[red]Run {run_id} not found[/red]")
                ctx.exit(1)

            job_id, parameters = run
            parameters_dict = json.loads(parameters) if parameters else None

        # Execute job
        console.print(f"[cyan]Retrying job {job_id} (run {run_id})...[/cyan]")
        executor = JobExecutor()
        result = executor.execute_job(
            job_id=job_id,
            dry_run=dry_run,
            parameters=parameters_dict,
        )

        if result.status == "success":
            console.print(
                f"[green]✓ Job {job_id} retried successfully[/green]\n"
                f"  Records loaded: {result.records_loaded}\n"
                f"  Duration: {result.duration_seconds:.2f}s\n"
                f"  New Run ID: {result.run_id}"
            )
        else:
            console.print(
                f"[red]✗ Job {job_id} failed on retry[/red]\n"
                f"  Error: {result.error_message}\n"
                f"  New Run ID: {result.run_id}"
            )
            ctx.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("cli_retry_error", error=str(e))
        ctx.exit(1)


@cli.command()
def list_jobs() -> None:
    """List all ETL jobs."""
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, source_endpoint, target_table, is_active,
                       requires_parameters, last_run_status, last_run_records
                FROM dw_etl_jobs
                ORDER BY id
                """
            )

            jobs = cursor.fetchall()

            if not jobs:
                console.print("[yellow]No jobs found[/yellow]")
                return

            # Display jobs
            table = Table(title="ETL Jobs")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Endpoint", style="blue")
            table.add_column("Target Table", style="magenta")
            table.add_column("Active", style="green")
            table.add_column("Parameters", style="yellow")
            table.add_column("Last Status", style="green")

            for job in jobs:
                (
                    job_id,
                    name,
                    endpoint,
                    target_table,
                    is_active,
                    requires_parameters,
                    last_status,
                    last_records,
                ) = job

                active_str = "[green]Yes[/green]" if is_active else "[red]No[/red]"
                params_str = "[yellow]Yes[/yellow]" if requires_parameters else "No"
                status_str = last_status or "N/A"

                table.add_row(
                    str(job_id),
                    name,
                    endpoint[:50] + "..." if len(endpoint) > 50 else endpoint,
                    target_table,
                    active_str,
                    params_str,
                    status_str,
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("cli_list_jobs_error", error=str(e))


def main() -> None:
    """Entry point for CLI."""
    cli()


if __name__ == "__main__":
    main()

