
echo "🔍 Instacart Data Mining Pipeline"
echo "================================================"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    echo "✅ Activating virtual environment..."
    source venv/bin/activate
else
    echo "❌ Error: Virtual environment not found!"
    exit 1
fi

# Check dependencies
echo "📦 Checking dependencies..."
python -c "import sklearn" 2>/dev/null || {
    echo "Installing scikit-learn..."
    pip install scikit-learn matplotlib seaborn mlxtend
}

# Parse command
MODE=${1:-all}

case $MODE in
    clustering)
        echo ""
        echo "🤖 Running Customer Clustering (K-Means)..."
        echo "================================================"
        python mining/customer_clustering.py
        ;;
    
    basket)
        echo ""
        echo "🛒 Running Market Basket Analysis (FP-Growth)..."
        echo "================================================"
        python mining/market_basket.py
        ;;
    
    recommend)
        echo ""
        echo "🎯 Running Recommendation Demo..."
        echo "================================================"
        python mining/recommendation.py
        ;;
    
    all)
        echo ""
        echo "🚀 Running Complete Mining Pipeline..."
        echo "================================================"
        
        echo ""
        echo "Step 1/3: Customer Clustering"
        python mining/customer_clustering.py
        
        echo ""
        echo "Step 2/3: Market Basket Analysis"
        python mining/market_basket.py
        
        echo ""
        echo "Step 3/3: Recommendation System"
        python mining/recommendation.py
        
        echo ""
        echo "================================================"
        echo "✅ All mining tasks complete!"
        ;;
    
    *)
        echo "❌ Invalid option: $MODE"
        echo ""
        echo "Usage: ./run_mining.sh [clustering|basket|recommend|all]"
        echo ""
        echo "Options:"
        echo "  clustering  - Run K-Means customer segmentation"
        echo "  basket      - Run market basket analysis"
        echo "  recommend   - Run recommendation demo"
        echo "  all         - Run complete pipeline (default)"
        exit 1
        ;;
esac

echo ""
echo "📁 Results saved to: mining/results/"
ls -lh mining/results/ 2>/dev/null || echo "   (No results yet)"
