# TrialSync ETL Web UI

Web-based interface for managing and monitoring ETL jobs.

## Features

- **Job Management**: View all ETL jobs, their status, and configuration
- **Job Execution**: Run individual jobs or all active jobs
- **Dry Run Mode**: Test job execution without writing to database
- **Execution History**: View detailed history of all job runs
- **Retry Failed Jobs**: Retry failed job runs with a single click
- **Real-time Status**: See job status, records loaded, and execution times

## Usage

### Starting the Web Server

```bash
# Start the FastAPI server
python -m src.web.server

# Or using uvicorn directly
uvicorn src.web.api:app --reload --port 8000
```

### Accessing the Web UI

1. Start the API server (see above)
2. Open your browser and navigate to:
   - **API Documentation**: http://localhost:8000/docs
   - **Web UI**: http://localhost:8000/ui

### API Endpoints

All CLI operations are available via REST API:

- `GET /jobs` - List all jobs
- `GET /jobs/{job_id}/status` - Get job status
- `GET /jobs/{job_id}/history` - Get job execution history
- `POST /jobs/{job_id}/run` - Run a single job
- `POST /jobs/run-all` - Run all active jobs
- `GET /runs` - Get all execution history
- `POST /runs/{run_id}/retry` - Retry a failed run

See http://localhost:8000/docs for complete API documentation.

## Development

The web UI is a single-page React application embedded in HTML. To modify:

1. Edit `web/index.html`
2. The React app uses Axios for API calls
3. API base URL is configured in the JavaScript (default: `http://localhost:8000`)

## Production Deployment

For production:

1. Update CORS settings in `src/web/api.py` to restrict origins
2. Serve static files through a proper web server (nginx, etc.)
3. Configure authentication/authorization
4. Update API_BASE URL in `web/index.html` to match your deployment

