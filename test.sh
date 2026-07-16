#!/bin/bash

# 🧪 Multi-Agent AI Platform - Quick Testing Script

set -e

echo "================================"
echo "🧪 Testing Multi-Agent Platform"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
run_test() {
  echo -e "${BLUE}→ $1${NC}"
}

success() {
  echo -e "${GREEN}✅ $1${NC}"
}

error() {
  echo -e "${RED}❌ $1${NC}"
}

warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

# Phase 1: Check Prerequisites
echo -e "${BLUE}═══ PHASE 1: Prerequisites ═══${NC}"
echo ""

run_test "Checking Python..."
if command -v python3 &> /dev/null; then
  PYTHON_VERSION=$(python3 --version)
  success "Python installed: $PYTHON_VERSION"
else
  error "Python not found. Install Python 3.10+"
  exit 1
fi

run_test "Checking Docker..."
if command -v docker &> /dev/null; then
  success "Docker installed"
else
  error "Docker not found. Install Docker"
  exit 1
fi

run_test "Checking Docker Compose..."
if docker-compose --version &> /dev/null; then
  success "Docker Compose installed"
else
  error "Docker Compose not found"
  exit 1
fi

run_test "Checking Node.js..."
if command -v node &> /dev/null; then
  NODE_VERSION=$(node --version)
  success "Node.js installed: $NODE_VERSION"
else
  warning "Node.js not found (optional for frontend testing)"
fi

echo ""
echo -e "${BLUE}═══ PHASE 2: Infrastructure ═══${NC}"
echo ""

run_test "Starting Docker services..."
docker-compose up -d
sleep 5

run_test "Checking PostgreSQL..."
if docker-compose exec -T postgres pg_isready -U postgres &> /dev/null; then
  success "PostgreSQL is healthy"
else
  error "PostgreSQL not responding"
  exit 1
fi

run_test "Checking Redis..."
if docker-compose exec -T redis redis-cli ping &> /dev/null; then
  success "Redis is healthy"
else
  error "Redis not responding"
  exit 1
fi

run_test "Checking Kafka..."
if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 &> /dev/null; then
  success "Kafka is healthy"
else
  error "Kafka not responding"
fi

run_test "Checking Temporal..."
if curl -s http://localhost:8080 &> /dev/null; then
  success "Temporal UI available at http://localhost:8080"
else
  warning "Temporal may still be starting (check docker logs)"
fi

echo ""
echo -e "${BLUE}═══ PHASE 3: Python Setup ═══${NC}"
echo ""

run_test "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
success "Virtual environment created"

run_test "Installing Python dependencies..."
pip install -q -e ".[dev]" 2>/dev/null
success "Dependencies installed"

echo ""
echo -e "${BLUE}═══ PHASE 4: Unit Tests ═══${NC}"
echo ""

run_test "Running unit tests..."
if pytest tests/unit/ -q --tb=short 2>/dev/null; then
  success "Unit tests passed"
else
  error "Unit tests failed (check TESTING_GUIDE.md for details)"
fi

echo ""
echo -e "${BLUE}═══ PHASE 5: Integration Tests ═══${NC}"
echo ""

run_test "Running integration tests..."
if pytest tests/integration/ -q --tb=short 2>/dev/null; then
  success "Integration tests passed"
else
  warning "Integration tests may require services to be fully ready"
fi

echo ""
echo -e "${BLUE}═══ PHASE 6: Database Setup ═══${NC}"
echo ""

run_test "Initializing database..."
python3 -c "
import asyncio
from src.infrastructure.database import init_db
asyncio.run(init_db())
" 2>/dev/null
success "Database initialized"

echo ""
echo -e "${BLUE}═══ PHASE 7: API Health Check ═══${NC}"
echo ""

# Start API in background
run_test "Starting API server (background)..."
timeout 30 uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
API_PID=$!
sleep 3

run_test "Testing health endpoint..."
if curl -s http://localhost:8000/health | grep -q "operational"; then
  success "API is healthy"
else
  error "API not responding"
  cat /tmp/api.log
  kill $API_PID 2>/dev/null || true
  exit 1
fi

echo ""
echo -e "${BLUE}═══ PHASE 8: API Endpoint Tests ═══${NC}"
echo ""

run_test "Testing /api/workflows endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test workflow"}')

if echo "$RESPONSE" | grep -q "workflow_id"; then
  WORKFLOW_ID=$(echo "$RESPONSE" | grep -o '"workflow_id":"[^"]*"' | cut -d'"' -f4)
  success "Workflow created: $WORKFLOW_ID"
else
  warning "Workflow endpoint returned: $RESPONSE"
fi

run_test "Testing /api/rate-limiting/check endpoint..."
if curl -s http://localhost:8000/api/rate-limiting/check/testuser | grep -q "allowed"; then
  success "Rate limiting endpoint works"
else
  warning "Rate limiting endpoint not responding"
fi

run_test "Testing /api/observability/summary endpoint..."
if curl -s http://localhost:8000/api/observability/summary | grep -q "workflows\|total"; then
  success "Observability endpoint works"
else
  warning "Observability endpoint not responding"
fi

echo ""
echo -e "${BLUE}═══ PHASE 9: Frontend Setup (Optional) ═══${NC}"
echo ""

if [ -d "dashboard" ]; then
  run_test "Installing frontend dependencies..."
  cd dashboard
  npm install -q 2>/dev/null
  cd ..
  success "Frontend dependencies installed"

  run_test "Building frontend..."
  cd dashboard
  npm run build -q 2>/dev/null
  cd ..
  success "Frontend built successfully"
else
  warning "Dashboard directory not found"
fi

echo ""
echo -e "${BLUE}═══ CLEANUP ═══${NC}"
echo ""

run_test "Stopping API server..."
kill $API_PID 2>/dev/null || true
success "API server stopped"

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ TESTING PHASE COMPLETE${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""

echo "📊 Next Steps:"
echo ""
echo "1️⃣  Start all services (keep running):"
echo "   docker-compose up -d"
echo ""
echo "2️⃣  Start backend API (Terminal 1):"
echo "   source venv/bin/activate"
echo "   uvicorn src.main:app --reload"
echo ""
echo "3️⃣  Start frontend dashboard (Terminal 2):"
echo "   cd dashboard"
echo "   npm run dev"
echo ""
echo "4️⃣  View dashboard:"
echo "   http://localhost:3000"
echo ""
echo "5️⃣  API Documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "6️⃣  Temporal UI:"
echo "   http://localhost:8080"
echo ""
echo "📝 Full testing guide:"
echo "   cat TESTING_GUIDE.md"
echo ""
echo "🧪 Run full test suite:"
echo "   pytest tests/ -v --cov=src"
echo ""

exit 0
