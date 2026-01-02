#!/bin/bash
# Startup script for TrialSync ETL Web Server

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Detect Python executable
if command -v python3.12 &> /dev/null; then
    PYTHON=python3.12
elif command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${RED}Error: Python not found. Please install Python 3.9+${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}Using Python ${PYTHON_VERSION}${NC}"

echo -e "${GREEN}Starting TrialSync ETL Web Server...${NC}"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    $PYTHON -m venv .venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing...${NC}"
    pip install -r requirements.txt
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Using .env.example if available.${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Please copy .env.example to .env and configure it.${NC}"
    fi
fi

# Check database connection (non-blocking)
echo -e "${GREEN}Checking database connection...${NC}"
DB_CHECK_OUTPUT=$(python -c "
import sys
try:
    from src.config import get_settings
    from src.db import get_pool
    s = get_settings()
    if not s.database.url:
        print('ERROR: DATABASE_URL not set in .env file')
        sys.exit(1)
    print(f'DATABASE_URL: {s.database.url[:50]}...')
    p = get_pool()
    p.initialize()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {str(e)}')
    sys.exit(1)
" 2>&1)

if echo "$DB_CHECK_OUTPUT" | grep -q "SUCCESS"; then
    echo -e "${GREEN}✓ Database connection OK${NC}"
elif echo "$DB_CHECK_OUTPUT" | grep -q "DATABASE_URL not set"; then
    echo -e "${YELLOW}⚠ ${DB_CHECK_OUTPUT}${NC}"
    echo -e "${YELLOW}  Server will start, but database operations will fail${NC}"
    echo -e "${YELLOW}  Please set DATABASE_URL in your .env file${NC}"
elif echo "$DB_CHECK_OUTPUT" | grep -q "ERROR"; then
    echo -e "${YELLOW}⚠ Database connection failed (server will start anyway)${NC}"
    echo -e "${YELLOW}  Error: $(echo "$DB_CHECK_OUTPUT" | grep ERROR | head -1)${NC}"
    echo -e "${YELLOW}  Troubleshooting:${NC}"
    echo -e "${YELLOW}    1. Check if PostgreSQL is running${NC}"
    echo -e "${YELLOW}    2. Verify DATABASE_URL in .env file${NC}"
    echo -e "${YELLOW}    3. Run: ./scripts/test-db-connection.sh${NC}"
    echo -e "${YELLOW}    4. See TROUBLESHOOTING.md for more help${NC}"
else
    echo -e "${YELLOW}⚠ Could not verify database connection${NC}"
fi
echo ""

# Start the server
echo -e "${GREEN}Starting server on http://localhost:8000${NC}"
echo -e "${GREEN}Web UI: http://localhost:8000/ui${NC}"
echo -e "${GREEN}API Docs: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

uvicorn src.web.api:app --reload --host 0.0.0.0 --port 8000

