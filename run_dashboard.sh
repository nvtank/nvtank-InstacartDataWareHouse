echo "🛒 Starting Instacart Analytics Dashboard..."
echo "================================================"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
else
    echo "❌ Error: Virtual environment not found!"
    echo "Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if streamlit is installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "📦 Installing dashboard dependencies..."
    pip install streamlit plotly
fi

# Check database connection
echo "🔍 Checking database connection..."
if docker ps | grep -q "instacart-mariadb"; then
    echo "✅ MariaDB container is running"
else
    echo "❌ Error: MariaDB container is not running!"
    echo "Please start it with: docker start instacart-mariadb"
    exit 1
fi

# Run Streamlit
echo ""
echo "🚀 Launching dashboard on http://localhost:8501"
echo "================================================"
echo ""
streamlit run dashboard/app.py
