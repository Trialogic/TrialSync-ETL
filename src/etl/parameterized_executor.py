from typing import List, Any, Sequence
import structlog

logger = structlog.get_logger(__name__)

class ParameterizedJobExecutor:
    """
    Executes a parameterized job by fetching parameter values from a source table/column,
    templating the source endpoint, calling the API client, and loading to staging via DataLoader.
    """

    def __init__(self, db_conn, api_client, data_loader, batch_size: int = 1000):
        self.db = db_conn
        self.api = api_client
        self.loader = data_loader
        self.batch_size = batch_size

    def fetch_parameters(self, table: str, column: str) -> List[Any]:
        sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
        with self.db.cursor() as cur:
            cur.execute(sql)
            rows: Sequence = cur.fetchall()
        return [row[0] for row in rows]

    def run(self, job_config: dict, run_id: int) -> int:
        """
        job_config keys:
          - id, name, source_endpoint, target_table, parameter_source_table, parameter_source_column
        Returns total records loaded.
        """
        params_table = job_config.get("parameter_source_table")
        params_column = job_config.get("parameter_source_column")
        if not params_table or not params_column:
            logger.warn("Parameterized job missing parameter source config", job=job_config.get("id"))
            return 0

        values = self.fetch_parameters(params_table, params_column)
        if not values:
            logger.info("No parameters to process", job=job_config.get("id"))
            return 0

        total = 0
        for value in values:
            endpoint = job_config["source_endpoint"].replace(f"{{{params_column}}}", str(value))
            # Fetch from API
            records = self.api.get_odata(endpoint)
            if records:
                self.loader.load_to_staging(
                    table_name=job_config["target_table"],
                    records=records,
                    job_id=job_config["id"],
                    run_id=run_id,
                )
                total += len(records)
        return total
