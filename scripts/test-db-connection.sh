#!/bin/bash
# Test database connection script

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Testing Database Connection...${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Load DATABASE_URL from .env
source .env 2>/dev/null || true

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}Error: DATABASE_URL not set in .env file${NC}"
    exit 1
fi

echo -e "${BLUE}DATABASE_URL:${NC} ${DATABASE_URL:0:50}..."
echo ""

# Test 1: Check if PostgreSQL is running
echo -e "${BLUE}Test 1: Checking if PostgreSQL is running...${NC}"
if command -v pg_isready &> /dev/null; then
    if pg_isready -h localhost -p 5432 &> /dev/null; then
        echo -e "${GREEN}✓ PostgreSQL is running${NC}"
    else
        echo -e "${RED}✗ PostgreSQL is not responding on localhost:5432${NC}"
        echo -e "${YELLOW}  Start PostgreSQL:${NC}"
        echo -e "${YELLOW}    macOS: brew services start postgresql${NC}"
        echo -e "${YELLOW}    Linux: sudo systemctl start postgresql${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ pg_isready not found, skipping check${NC}"
fi
echo ""

# Test 2: Test connection with psql
echo -e "${BLUE}Test 2: Testing connection with psql...${NC}"
if command -v psql &> /dev/null; then
    if psql "$DATABASE_URL" -c "SELECT 1;" &> /dev/null; then
        echo -e "${GREEN}✓ psql connection successful${NC}"
    else
        echo -e "${RED}✗ psql connection failed${NC}"
        echo -e "${YELLOW}  Common issues:${NC}"
        echo -e "${YELLOW}    - Database doesn't exist${NC}"
        echo -e "${YELLOW}    - Wrong username/password${NC}"
        echo -e "${YELLOW}    - Wrong host/port${NC}"
        echo ""
        echo -e "${YELLOW}  Try creating the database:${NC}"
        echo -e "${YELLOW}    createdb trialsync_dev${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ psql not found, skipping check${NC}"
fi
echo ""

# Test 3: Test with Python
echo -e "${BLUE}Test 3: Testing connection with Python...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON_OUTPUT=$(python -c "
from src.config import get_settings
from src.db import get_pool
try:
    s = get_settings()
    if not s.database.url:
        print('ERROR: DATABASE_URL not set')
        exit(1)
    p = get_pool()
    p.initialize()
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {str(e)}')
    exit(1)
" 2>&1)
    
    if echo "$PYTHON_OUTPUT" | grep -q "SUCCESS"; then
        echo -e "${GREEN}✓ Python connection successful${NC}"
    else
        echo -e "${RED}✗ Python connection failed${NC}"
        echo -e "${YELLOW}  Error: $(echo "$PYTHON_OUTPUT" | grep ERROR || echo 'Unknown error')${NC}"
        echo -e "${YELLOW}  Make sure virtual environment is activated and dependencies are installed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Virtual environment not found, skipping Python test${NC}"
fi
echo ""

echo -e "${GREEN}All database connection tests passed!${NC}"

