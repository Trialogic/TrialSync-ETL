# Quick Fix: Database Connection

If you're seeing "Database connection failed" warning, here's how to fix it:

## Quick Diagnosis

Run this command to test your database connection:
```bash
./scripts/test-db-connection.sh
```

## Common Solutions

### 1. PostgreSQL Not Installed or Not Running

**Check if PostgreSQL is installed:**
```bash
# macOS
brew list | grep postgresql

# Check if running
brew services list | grep postgresql
```

**Install/Start PostgreSQL:**

**macOS (Homebrew):**
```bash
# Install
brew install postgresql@16

# Start service
brew services start postgresql@16

# Or start manually
pg_ctl -D /usr/local/var/postgresql@16 start
```

**macOS (Postgres.app):**
- Download from https://postgresapp.com/
- Install and start the app

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-16
sudo systemctl start postgresql

# Or
sudo service postgresql start
```

### 2. Database Doesn't Exist

**Create the database:**
```bash
# Using createdb (if available)
createdb trialsync_dev

# Or using psql
psql postgres -c "CREATE DATABASE trialsync_dev;"
```

**If psql is not in PATH:**
```bash
# macOS (Homebrew)
/usr/local/opt/postgresql@16/bin/psql postgres -c "CREATE DATABASE trialsync_dev;"

# Or find psql
which psql
find /usr -name psql 2>/dev/null
```

### 3. Update .env File

Make sure your `.env` file has the correct DATABASE_URL:

```env
# Format: postgresql://username@host:port/database_name
DATABASE_URL=postgresql://chrisprader@localhost:5432/trialsync_dev

# If you need a password:
DATABASE_URL=postgresql://username:password@localhost:5432/trialsync_dev
```

**Test the connection string:**
```bash
# If psql is available
psql "postgresql://chrisprader@localhost:5432/trialsync_dev" -c "SELECT 1;"

# If not, test with Python (after activating venv)
source .venv/bin/activate
python -c "
from src.config import get_settings
from src.db import get_pool
s = get_settings()
p = get_pool()
p.initialize()
print('Connection successful!')
"
```

### 4. Wrong Port

PostgreSQL default port is 5432. If yours is different:

```bash
# Check what port PostgreSQL is using
# macOS (Homebrew)
cat /usr/local/var/postgresql@16/postgresql.conf | grep port

# Or check if something is listening on 5432
lsof -i :5432
```

Update `.env` with correct port:
```env
DATABASE_URL=postgresql://chrisprader@localhost:5433/trialsync_dev  # if port is 5433
```

### 5. User Permissions

**Create user and grant permissions:**
```bash
# Connect to postgres database
psql postgres

# Then run:
CREATE USER chrisprader;
CREATE DATABASE trialsync_dev OWNER chrisprader;
GRANT ALL PRIVILEGES ON DATABASE trialsync_dev TO chrisprader;
\q
```

## Minimal Setup (For Development)

If you just want to get started quickly:

1. **Install PostgreSQL** (if not installed)
2. **Create database:**
   ```bash
   createdb trialsync_dev
   ```
3. **Update .env:**
   ```env
   DATABASE_URL=postgresql://$(whoami)@localhost:5432/trialsync_dev
   ENVIRONMENT=development
   DRY_RUN=true
   ```
4. **Test:**
   ```bash
   ./scripts/test-db-connection.sh
   ```

## Server Will Still Start

**Important:** The server will start even if the database connection fails. This allows you to:
- View the API documentation
- Test the web UI
- See what endpoints are available

However, you won't be able to:
- Run ETL jobs
- View job status
- Access execution history

## Need More Help?

- See `TROUBLESHOOTING.md` for detailed troubleshooting
- Check PostgreSQL logs for connection errors
- Verify your PostgreSQL installation is working: `psql --version`

