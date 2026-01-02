# Troubleshooting Guide

Common issues and solutions for TrialSync ETL.

## Database Connection Issues

### Warning: Database connection failed

**Symptoms:**
- Startup script shows: "Warning: Database connection failed"
- Server starts but can't connect to database

**Diagnosis:**

Run the database connection test:
```bash
./scripts/test-db-connection.sh
```

**Common Causes & Solutions:**

#### 1. PostgreSQL Not Running

**Check:**
```bash
# macOS
brew services list | grep postgresql

# Linux
sudo systemctl status postgresql

# Or test directly
pg_isready -h localhost -p 5432
```

**Fix:**
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql

# Or start manually
postgres -D /usr/local/var/postgres  # macOS default location
```

#### 2. Database Doesn't Exist

**Check:**
```bash
psql -l | grep trialsync
```

**Fix:**
```bash
# Create the database
createdb trialsync_dev

# Or using psql
psql postgres -c "CREATE DATABASE trialsync_dev;"
```

#### 3. Wrong DATABASE_URL Format

**Current format in .env:**
```env
DATABASE_URL=postgresql://chrisprader@localhost:5432/trialsync_dev
```

**Correct formats:**
```env
# Without password (local development)
DATABASE_URL=postgresql://username@localhost:5432/database_name

# With password
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# With all options
DATABASE_URL=postgresql://username:password@host:port/database_name
```

**Test your connection string:**
```bash
psql "postgresql://chrisprader@localhost:5432/trialsync_dev" -c "SELECT 1;"
```

#### 4. Wrong Username or Permissions

**Check current user:**
```bash
whoami
psql postgres -c "SELECT current_user;"
```

**Fix:**
- Update DATABASE_URL with correct username
- Or create user and grant permissions:
  ```sql
  CREATE USER chrisprader;
  GRANT ALL PRIVILEGES ON DATABASE trialsync_dev TO chrisprader;
  ```

#### 5. Wrong Port

**Check PostgreSQL port:**
```bash
# macOS (Homebrew)
cat /usr/local/var/postgres/postgresql.conf | grep port

# Linux
sudo cat /etc/postgresql/*/main/postgresql.conf | grep port

# Or check what's listening
lsof -i :5432
```

**Fix:**
- Update DATABASE_URL with correct port (default is 5432)

#### 6. Connection Refused

**Symptoms:**
- `psql: error: connection to server at "localhost" (::1), port 5432 failed`

**Possible causes:**
- PostgreSQL not running
- Wrong host (try `127.0.0.1` instead of `localhost`)
- Firewall blocking connection
- PostgreSQL configured to not accept connections

**Fix:**
```bash
# Check PostgreSQL is listening
netstat -an | grep 5432

# Check pg_hba.conf allows connections
# Location: /usr/local/var/postgres/pg_hba.conf (macOS Homebrew)
# Should have: host all all 127.0.0.1/32 trust
```

## Python/Module Issues

### ModuleNotFoundError

**Symptoms:**
- `ModuleNotFoundError: No module named 'yaml'`
- `ModuleNotFoundError: No module named 'fastapi'`

**Fix:**
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep -E "fastapi|yaml|uvicorn"
```

### Python Version Issues

**Symptoms:**
- Script can't find Python
- Wrong Python version

**Fix:**
```bash
# Check available Python versions
which python3 python3.12 python

# Use the setup script (auto-detects)
./scripts/setup-dev.sh

# Or manually specify Python
python3 -m venv .venv
```

## Environment Variable Issues

### DATABASE_URL Not Set

**Symptoms:**
- "DATABASE_URL not set in .env file"

**Fix:**
```bash
# Check if .env exists
ls -la .env

# Create from example
cp .env.example .env

# Edit with your settings
nano .env  # or your preferred editor
```

### Environment Variables Not Loading

**Fix:**
```bash
# Test if variables are loaded
source .env
echo $DATABASE_URL

# Or test with Python
python -c "from src.config import get_settings; s = get_settings(); print(s.database.url)"
```

## Port Already in Use

### Address Already in Use (port 8000)

**Fix:**
```bash
# Find process using port 8000
lsof -ti:8000

# Kill the process
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn src.web.api:app --port 8001
```

## Permission Issues

### Permission Denied on Scripts

**Fix:**
```bash
chmod +x scripts/*.sh
```

### Permission Denied on Database

**Symptoms:**
- `permission denied for database`

**Fix:**
```sql
-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE trialsync_dev TO your_username;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_username;
```

## Quick Diagnostic Commands

```bash
# Test database connection
./scripts/test-db-connection.sh

# Check Python setup
python --version
which python
pip list | head -20

# Check environment
echo $DATABASE_URL
cat .env | grep -v "^#" | grep -v "^$"

# Test imports
python -c "import fastapi, uvicorn, click, rich, structlog; print('OK')"

# Check PostgreSQL
pg_isready
psql -l
```

## Getting More Help

1. Check the logs for detailed error messages
2. Run with verbose output: `uvicorn src.web.api:app --log-level debug`
3. Test individual components:
   - Database: `./scripts/test-db-connection.sh`
   - Config: `python -c "from src.config import get_settings; print(get_settings())"`
   - API Client: `python -c "from src.api import ClinicalConductorClient; print('OK')"`

## Still Having Issues?

1. Verify all prerequisites are installed
2. Run the setup script: `./scripts/setup-dev.sh`
3. Check `DEV_SETUP.md` for detailed setup instructions
4. Review error messages carefully - they usually indicate the specific issue

