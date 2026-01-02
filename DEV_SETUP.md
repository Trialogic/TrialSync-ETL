# Development Environment Setup

Complete guide for setting up the TrialSync ETL development environment.

## Prerequisites

- **Python 3.9+** (3.12 recommended)
- **PostgreSQL 16** (running and accessible)
- **Git** (for cloning the repository)

## Quick Setup (Automated)

Run the setup script:

```bash
# Make script executable (if needed)
chmod +x scripts/setup-dev.sh

# Run setup
./scripts/setup-dev.sh
```

This script will:
1. Detect and verify Python installation
2. Create virtual environment
3. Install all dependencies
4. Create `.env` file from `.env.example`
5. Verify installation
6. Test database connection (optional)

## Manual Setup

If you prefer to set up manually:

### 1. Check Python Version

```bash
python3 --version
# Should be Python 3.9 or higher
```

If Python 3.9+ is not available, install it:
- **macOS**: `brew install python@3.12`
- **Linux**: `sudo apt-get install python3.12` (or use your package manager)
- **Windows**: Download from [python.org](https://www.python.org/downloads/)

### 2. Create Virtual Environment

```bash
# Use python3, python3.12, or python depending on what's available
python3 -m venv .venv

# Or if you have python3.12 specifically
python3.12 -m venv .venv
```

### 3. Activate Virtual Environment

**macOS/Linux:**
```bash
source .venv/bin/activate
```

**Windows:**
```cmd
.venv\Scripts\activate
```

You should see `(.venv)` in your prompt.

### 4. Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit with your settings
nano .env  # or use your preferred editor
```

**Required variables:**
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/trialsync_dev

# Clinical Conductor API
CC_API_BASE_URL=https://your-api-url.com
CC_API_KEY=your-api-key

# Environment
ENVIRONMENT=development
DRY_RUN=true  # Set to false for production
```

### 7. Verify Installation

```bash
# Test Python imports
python -c "import fastapi, uvicorn, click, rich, structlog; print('✓ All imports successful')"

# Test database connection (if configured)
python -c "from src.config import get_settings; from src.db import get_pool; s = get_settings(); p = get_pool(); p.initialize(); print('✓ Database connection OK')"
```

## Starting the Services

### Option 1: Using the Startup Script

```bash
./scripts/start-server.sh
```

### Option 2: Using Python Module

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Start server
python -m src.web.server
```

### Option 3: Using uvicorn Directly

```bash
source .venv/bin/activate
uvicorn src.web.api:app --reload --port 8000
```

## Troubleshooting

### Python Not Found

**Issue**: `python3.12: command not found`

**Solutions**:
1. Use `python3` instead (the startup script auto-detects this)
2. Install Python 3.12:
   - macOS: `brew install python@3.12`
   - Linux: Use your package manager
   - Windows: Download from python.org

### Virtual Environment Issues

**Issue**: `No module named venv`

**Solution**: Install python3-venv package:
```bash
# Ubuntu/Debian
sudo apt-get install python3-venv

# macOS (usually included)
# If missing, reinstall Python
```

### Import Errors

**Issue**: `ModuleNotFoundError` when running

**Solutions**:
1. Make sure virtual environment is activated (`source .venv/bin/activate`)
2. Reinstall dependencies: `pip install -r requirements.txt`
3. Check Python version: `python --version` (should be 3.9+)

### Database Connection Errors

**Issue**: `Database connection failed`

**Solutions**:
1. Check PostgreSQL is running:
   ```bash
   # macOS
   brew services list | grep postgresql
   
   # Linux
   sudo systemctl status postgresql
   ```

2. Verify DATABASE_URL in `.env`:
   ```bash
   # Format: postgresql://user:password@host:port/database
   DATABASE_URL=postgresql://chrisprader@localhost:5432/trialsync_dev
   ```

3. Test connection manually:
   ```bash
   psql $DATABASE_URL -c "SELECT 1;"
   ```

### Port Already in Use

**Issue**: `Address already in use` on port 8000

**Solutions**:
1. Find and kill the process:
   ```bash
   # macOS/Linux
   lsof -ti:8000 | xargs kill -9
   
   # Or use a different port
   uvicorn src.web.api:app --port 8001
   ```

### Permission Denied on Scripts

**Issue**: `Permission denied` when running scripts

**Solution**:
```bash
chmod +x scripts/*.sh
```

## Development Workflow

### Daily Development

1. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Start the server:
   ```bash
   python -m src.web.server
   ```

3. Make code changes (server auto-reloads)

4. Test in browser: http://localhost:8000/ui

### Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/test_config.py

# Run with coverage
pytest --cov=src tests/
```

### Code Quality Checks

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/
pylint src/
```

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true
}
```

### PyCharm

1. Open project
2. Go to Settings → Project → Python Interpreter
3. Select `.venv/bin/python` as interpreter
4. Enable Black and isort as external tools

## Next Steps

After setup is complete:

1. **Start the server**: `./scripts/start-server.sh`
2. **Access Web UI**: http://localhost:8000/ui
3. **View API Docs**: http://localhost:8000/docs
4. **Run a test job**: Use the Web UI or CLI

## Getting Help

- Check `STARTUP.md` for startup instructions
- Check `README.md` for project overview
- Review `docs/` directory for detailed documentation
- Check logs for error messages

