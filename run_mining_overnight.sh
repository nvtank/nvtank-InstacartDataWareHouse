#!/bin/bash

# Script to run mining pipeline overnight with full dataset
# Output will be logged to mining_overnight.log

echo "🌙 Instacart Overnight Mining Pipeline"
echo "================================================"
echo ""
echo "⏰ Started at: $(date)"
echo "📊 Processing FULL DATASET (all 3.3M orders)"
echo "⏱️  Estimated time: 1-2 hours"
echo ""
echo "📝 Logging to: mining_overnight.log"
echo "================================================"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Error: Virtual environment not found!"
    exit 1
fi

# Run with nohup to keep running even if terminal closes
# Redirect both stdout and stderr to log file
nohup bash -c '
    echo "🚀 Starting mining pipeline at $(date)"
    echo ""
    
    echo "Step 1/3: Customer Clustering"
    python mining/customer_clustering.py
    
    echo ""
    echo "Step 2/3: Market Basket Analysis (FULL DATASET)"
    python mining/market_basket.py
    
    echo ""
    echo "Step 3/3: Recommendation System"
    python mining/recommendation.py
    
    echo ""
    echo "================================================"
    echo "✅ All mining tasks complete at $(date)!"
    echo "================================================"
' > mining_overnight.log 2>&1 &

# Get the process ID
PID=$!
echo "✅ Mining pipeline started in background (PID: $PID)"
echo ""
echo "📊 To monitor progress:"
echo "   tail -f mining_overnight.log"
echo ""
echo "🔍 To check if still running:"
echo "   ps aux | grep $PID"
echo ""
echo "⏹️  To stop (if needed):"
echo "   kill $PID"
echo ""
echo "📁 Results will be saved to: mining/results/"
echo ""
