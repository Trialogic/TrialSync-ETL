# TrialSync ETL - Startup Guide

This guide explains how to start the TrialSync ETL services from the terminal.

## Prerequisites

- Python 3.12+
- PostgreSQL 16 (running and accessible)
- Environment variables configured (see `.env.example`)

## Quick Start

### 1. Set Up Environment

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# OR
.venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Required variables:
# - DATABASE_URL
# - CC_API_BASE_URL
# - CC_API_KEY
# - ENVIRONMENT
# - DRY_RUN
```

### 3. Start the Web Server

```bash
# Option 1: Using the server module
python -m src.web.server

# Option 2: Using uvicorn directly
uvicorn src.web.api:app --reload --port 8000

# Option 3: Using the startup script
./scripts/start-server.sh
```

### 4. Access the Services

Once the server is running, you can access:

- **Web UI**: http://localhost:8000/ui
- **API Documentation**: http://localhost:8000/docs
- **API Root**: http://localhost:8000/
- **Health Check**: http://localhost:8000/health

## Using the CLI

While the web server is running, you can also use the CLI:

```bash
# List all jobs
python -m src.cli.main list-jobs

# Run a single job
python -m src.cli.main run --job-id 1

# Run all active jobs
python -m src.cli.main run --all

# Run with dry-run mode
python -m src.cli.main run --job-id 1 --dry-run

# Check job status
python -m src.cli.main status --job-id 1

# View execution history
python -m src.cli.main history --limit 20

# Retry a failed run
python -m src.cli.main retry --run-id 123
```

## Development Mode

For development with auto-reload:

```bash
# Start server with auto-reload
uvicorn src.web.api:app --reload --port 8000 --host 0.0.0.0
```

## Production Mode

For production:

```bash
# Start server with multiple workers
uvicorn src.web.api:app --host 0.0.0.0 --port 8000 --workers 4
```

## Troubleshooting

### Database Connection Issues

```bash
# Test database connection
psql $DATABASE_URL -c "SELECT 1;"

# Check if database is accessible
python -c "from src.db import get_pool; pool = get_pool(); pool.initialize(); print('Connected!')"
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
uvicorn src.web.api:app --port 8001
```

### Environment Variables Not Loaded

```bash
# Verify environment variables are set
python -c "from src.config import get_settings; s = get_settings(); print(s.database.url)"
```

## Background Process

To run the server in the background:

```bash
# Using nohup (Linux/macOS)
nohup uvicorn src.web.api:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &

# Using screen
screen -S trialsync-etl
uvicorn src.web.api:app --host 0.0.0.0 --port 8000
# Press Ctrl+A then D to detach

# Using tmux
tmux new -s trialsync-etl
uvicorn src.web.api:app --host 0.0.0.0 --port 8000
# Press Ctrl+B then D to detach
```

## Stopping the Server

```bash
# If running in foreground: Press Ctrl+C

# If running in background: Find and kill the process
ps aux | grep uvicorn
kill <PID>
```

