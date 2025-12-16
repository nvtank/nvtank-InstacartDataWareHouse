set -e  # Exit on error

echo "🛒 INSTACART DATA WAREHOUSE - COMPLETE WORKFLOW"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ================================================
# STEP 0: Prerequisites Check
# ================================================
echo -e "${BLUE}📋 Step 0: Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found! Please install Docker first.${NC}"
    exit 1
fi
echo "✅ Docker installed"

# Check Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python not found! Please install Python 3.13.${NC}"
    exit 1
fi
echo "✅ Python installed"

# Check Docker container
if ! docker ps | grep -q "instacart-mariadb"; then
    echo "⚠️  MariaDB container not running. Starting..."
    docker start instacart-mariadb || {
        echo -e "${RED}❌ Failed to start container. Please check Docker.${NC}"
        exit 1
    }
    sleep 5
fi
echo "✅ MariaDB container running"

# ================================================
# STEP 1: Setup Python Environment
# ================================================
echo ""
echo -e "${BLUE}🐍 Step 1: Setting up Python environment...${NC}"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

source venv/bin/activate
echo "✅ Virtual environment activated"

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# ================================================
# STEP 2: Create Database Schema
# ================================================
echo ""
echo -e "${BLUE}🗄️  Step 2: Creating database schema...${NC}"

cd sql
./run_all_sql.sh
cd ..

# Verify schema
TABLE_COUNT=$(docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh -e "SHOW TABLES;" | wc -l)
if [ "$TABLE_COUNT" -lt 7 ]; then
    echo -e "${RED}❌ Schema creation failed! Expected 7 tables.${NC}"
    exit 1
fi
echo "✅ Database schema created (7 tables)"

# ================================================
# STEP 3: Run ETL Pipeline
# ================================================
echo ""
echo -e "${BLUE}📥 Step 3: Running ETL pipeline...${NC}"
echo "⏱️  This will take 30-45 minutes. Please wait..."

python etl/etl_pipeline.py

# Verify data loaded
ROW_COUNT=$(docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh -e "SELECT COUNT(*) FROM Fact_Orders;" | tail -n 1)
if [ "$ROW_COUNT" -lt 1000000 ]; then
    echo -e "${RED}❌ ETL failed! Expected millions of rows.${NC}"
    exit 1
fi
echo "✅ ETL complete ($ROW_COUNT orders loaded)"

# ================================================
# STEP 4: Test SQL Queries
# ================================================
echo ""
echo -e "${BLUE}📊 Step 4: Testing SQL queries...${NC}"

cd analysis
docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh < 11_summary_statistics.sql > ../summary_results.txt
cd ..

echo "✅ SQL queries tested (see summary_results.txt)"

# ================================================
# STEP 5: Run Data Mining
# ================================================
echo ""
echo -e "${BLUE}🤖 Step 5: Running data mining...${NC}"
echo "⏱️  This will take 5-10 minutes. Please wait..."

./run_mining.sh all

echo "✅ Data mining complete (see mining/results/)"

# ================================================
# STEP 6: Launch Dashboard
# ================================================
echo ""
echo -e "${BLUE}🎨 Step 6: Launching dashboard...${NC}"
echo ""
echo "================================================"
echo -e "${GREEN}✅ ALL STEPS COMPLETE!${NC}"
echo "================================================"
echo ""
echo "📁 Generated files:"
echo "   - Database: 36.6M rows in 7 tables"
echo "   - SQL results: summary_results.txt"
echo "   - Mining results: mining/results/*.png, *.csv"
echo ""
echo "🚀 Starting Streamlit dashboard..."
echo "   Local URL: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo "================================================"

# Launch dashboard (blocking)
streamlit run dashboard/app.py

# Cleanup on exit
trap "echo 'Stopping dashboard...'; exit" INT TERM
