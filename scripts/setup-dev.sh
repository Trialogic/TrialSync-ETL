#!/bin/bash
# Development environment setup script for TrialSync ETL

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrialSync ETL - Development Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Detect Python executable
if command -v python3.12 &> /dev/null; then
    PYTHON=python3.12
    PYTHON_CMD="python3.12"
elif command -v python3 &> /dev/null; then
    PYTHON=python3
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON=python
    PYTHON_CMD="python"
else
    echo -e "${RED}Error: Python not found. Please install Python 3.9+${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR_VERSION" -lt 3 ] || ([ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -lt 9 ]); then
    echo -e "${RED}Error: Python 3.9+ required. Found Python ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Step 1: Create virtual environment
echo ""
echo -e "${BLUE}Step 1: Setting up virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Step 2: Activate and upgrade pip
echo ""
echo -e "${BLUE}Step 2: Activating virtual environment and upgrading pip...${NC}"
source .venv/bin/activate
$PYTHON -m pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓ pip upgraded${NC}"

# Step 3: Install dependencies
echo ""
echo -e "${BLUE}Step 3: Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}Error: requirements.txt not found${NC}"
    exit 1
fi

# Step 4: Check for .env file
echo ""
echo -e "${BLUE}Step 4: Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}⚠ Please edit .env with your configuration:${NC}"
        echo -e "${YELLOW}  - DATABASE_URL${NC}"
        echo -e "${YELLOW}  - CC_API_BASE_URL${NC}"
        echo -e "${YELLOW}  - CC_API_KEY${NC}"
    else
        echo -e "${RED}Warning: .env.example not found${NC}"
        echo -e "${YELLOW}Creating minimal .env file...${NC}"
        cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/trialsync_dev

# Clinical Conductor API Configuration
CC_API_BASE_URL=https://test-api.example.com
CC_API_KEY=your-api-key-here

# Environment
ENVIRONMENT=development
DRY_RUN=true
EOF
        echo -e "${YELLOW}⚠ Please edit .env with your actual configuration${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Step 5: Verify installation
echo ""
echo -e "${BLUE}Step 5: Verifying installation...${NC}"
if $PYTHON -c "import fastapi, uvicorn, click, rich, structlog" 2>/dev/null; then
    echo -e "${GREEN}✓ Core dependencies verified${NC}"
else
    echo -e "${RED}Error: Some dependencies are missing${NC}"
    exit 1
fi

# Step 6: Test database connection (optional)
echo ""
echo -e "${BLUE}Step 6: Testing database connection (optional)...${NC}"
if $PYTHON -c "from src.config import get_settings; from src.db import get_pool; s = get_settings(); p = get_pool(); p.initialize()" 2>/dev/null; then
    echo -e "${GREEN}✓ Database connection successful${NC}"
else
    echo -e "${YELLOW}⚠ Database connection failed (this is OK if database is not configured yet)${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "To start the server, run:"
echo -e "  ${GREEN}./scripts/start-server.sh${NC}"
echo ""
echo -e "Or manually:"
echo -e "  ${GREEN}source .venv/bin/activate${NC}"
echo -e "  ${GREEN}python -m src.web.server${NC}"
echo ""
echo -e "Then access:"
echo -e "  ${BLUE}Web UI:${NC} http://localhost:8000/ui"
echo -e "  ${BLUE}API Docs:${NC} http://localhost:8000/docs"
echo ""

